from collections import defaultdict
from datetime import date, datetime, time, timedelta
from functools import partial, reduce
from itertools import (accumulate, chain, islice, pairwise, repeat,
                       starmap, takewhile, tee)
from multiprocessing.dummy import Pool
from operator import eq, gt, itemgetter, or_
from typing import Iterable, Optional, Tuple

import requests
from more_itertools import (before_and_after, flatten, grouper, ilen,
                            tail, unzip)
from tqdm import tqdm

API_URL_GET_ACCOUNT_INFO = r'https://www.nlb.gov.sg/seatbooking/api/accounts/GetAccountInfo'
API_URL_SEARCH_AVAILABLE_AREAS = r'https://www.nlb.gov.sg/seatbooking/api/areas/SearchAvailableAreas'
API_HEADERS = {'referer': r'https://www.nlb.gov.sg/'}

def compose(*fs):
    compose2 = lambda f, g: lambda *args, **kwargs: f(g(*args, **kwargs))
    return reduce(compose2, fs)

def effect(f):
    def affect(x):
        f(x)
        return x
    return affect

def api_get_account_info():
    return requests.get(
        API_URL_GET_ACCOUNT_INFO,
        headers=API_HEADERS
    ).json()

def api_search_available_areas(branch_id: int, start_time: datetime, duration: timedelta):
    return requests.get(
        API_URL_SEARCH_AVAILABLE_AREAS,
        headers=API_HEADERS,
        params={
            'Mode': 'OffsiteMode',
            'BranchId': branch_id,
            'StartTime': start_time.isoformat(),
            'DurationInMinutes': int(duration.total_seconds()) // 60 }
     ).json()

def range_generic(start, end, step):
    return takewhile(
        partial(gt, end),
        accumulate(repeat(step), initial=start))

def json_get_available_branch_props(data) -> Tuple[Iterable[int], Iterable[str]]:
    data = data['settings']['menus']['branchMenus']
    attrs = compose(lambda f: map(f, filter(compose(bool, itemgetter('areas')), data)), itemgetter)
    branch_ids = attrs('id')
    branch_names = attrs('name')
    return branch_ids, branch_names

def json_get_area_props(data, branch_id: int) -> Tuple[Iterable[str], Iterable[time], Iterable[time]]:
    data = next(filter(
        compose(partial(eq, branch_id), itemgetter('id')),
        data['settings']['menus']['branchMenus']))
    data = data['areas']
    attrs = compose(lambda f: map(f, data), itemgetter)
    area_names = attrs('name')
    parse_time = compose(datetime.time, datetime.fromisoformat)
    opening_times = map(parse_time, attrs('openingTime'))
    closing_times = map(parse_time, attrs('closingTime'))
    return area_names, opening_times, closing_times

def json_get_available_seats(data) -> Iterable[Tuple[str, Iterable[str]]]:
    return (
        (f'{area["areaName"]}, Level {area["floor"]}', (
            seat['name']
            for seat in area['availableSeats']))
        for area in data['areas'])

def densify(xs, ys):
    xss = accumulate(
        ys,
        lambda xs, y: (
            lambda xs1, xs2: (xs1, islice(xs2, 1, None))
        )(*before_and_after(partial(gt, y), xs[1])),
        initial=([], xs))
    xss1, xss2 = tee(xss)
    xss = islice(xss1, 1, None)
    xss = map(itemgetter(0), xss)
    xss = chain(xss, map(itemgetter(1), tail(1, xss2)))
    ns = map(ilen, xss)
    bss = map(
        compose(
            partial(chain, [True]),
            partial(repeat, False)),
        ns)
    bs = islice(flatten(bss), 1, None)
    return bs

def decode(bs):
    '''
    api availability search duration cannot be lower than 30 mins,
    but since booking duration must be min 30 mins, we can use this
    function to recover mostly the 15 mins seat availability. the
    only lost info is if seat avails is [t,f,...], it would be seen
    as [f,f,...], but for all other sequences, it's fine.
    '''
    return starmap(or_, pairwise(chain([False], bs)))

def get_seat_availabilities_today(
        data, branch_id: int,
        interval_duration: timedelta = timedelta(minutes=15),
        api_search_duration: timedelta = timedelta(minutes=30),
        start_time: Optional[time] = None, end_time: Optional[time] = None,
        truncate_start: bool = True, align_start_minute: Optional[int] = 15,
        tomorrow: bool = False, max_concurrent_api_calls: Optional[int] = None):
    area_names, opening_times, closing_times = json_get_area_props(data, branch_id)
    if start_time is None: start_time = min(opening_times)
    if end_time is None: end_time = max(closing_times)
    add_today = partial(datetime.combine, date.today())
    start_time = add_today(start_time)
    end_time = add_today(end_time)
    if tomorrow:
        start_time += timedelta(days=1)
        end_time += timedelta(days=1)
    if truncate_start:
        start_time = max(start_time, datetime.now())
    if align_start_minute is not None:
        align_minute = (start_time.minute // align_start_minute) * align_start_minute
        start_time = datetime(
            start_time.year, start_time.month,
            start_time.day, start_time.hour,
            align_minute) + timedelta(minutes=align_start_minute)
    intervals = range_generic(start_time, end_time, interval_duration)
    intervals = list(intervals)
    with Pool(processes=max_concurrent_api_calls) as pool:
        interval_area_seats = pool.imap(
            compose(
                json_get_available_seats,
                partial(api_search_available_areas, branch_id, duration=api_search_duration)),
            intervals)
        area_seat_intervals = { name: defaultdict(list) for name in area_names }
        area_seat_intervals = reduce(
            lambda area_seat_intervals, x : (
                lambda interval, area_seats: (
                    reduce(
                        lambda area_seat_intervals, x: (
                            lambda area, seats: (
                                reduce(
                                    lambda area_seat_intervals, seat: (
                                        effect(lambda area_seat_intervals: (
                                            area_seat_intervals[area][seat].append(interval))
                                        )(area_seat_intervals)),
                                    seats, area_seat_intervals)                            
                            ))(*x),
                        area_seats, area_seat_intervals)
                ))(*x),
            zip(
                tqdm(intervals, desc=f'Max concurrent api calls: {pool._processes}'),
                interval_area_seats),
            area_seat_intervals)
    seat_availabilities = flatten(map(
        lambda x: (lambda area, seat_intervals: (
            map(
                lambda x: (lambda seat, seat_interval: (
                    ((area, seat), decode(densify(intervals, seat_interval)))
                ))(*x),
                sorted(seat_intervals.items(), key=compose(
                    lambda x: (len(x), x),
                    itemgetter(0)))
            )))(*x),
        area_seat_intervals.items()))
    return start_time, end_time, seat_availabilities

def print_branches(branch_ids: Iterable[int], branch_names: Iterable[str]):
    print('ID | Name')
    for branch_id, branch_name in zip(branch_ids, branch_names):
        print(str(branch_id).rjust(2), end=' | ')
        print(branch_name)

def print_seat_availabilities(
        start_time: datetime, end_time: datetime,
        seat_availabilities: Iterable[Tuple[Tuple[str, str], Iterable[bool]]],
        available_symbol='.', not_available_symbol='#', unknown_symbol=' ',
        time_header_interval=30):
    try:
        area_seat_names, availabilities = unzip(seat_availabilities)
    except ValueError: # If can't unzip, means no data
        print('No data to display')
        return
    name = lambda area, seat: f'{area}, {seat}'
    names = list(starmap(name, area_seat_names))
    name_pad = max(map(len, names), default=0)
    names = map(lambda s: s.ljust(name_pad), names)
    align = start_time.minute // 15
    symbol = lambda b: available_symbol if b else not_available_symbol
    availabilities = map(
        compose(
            partial(grouper, n=4, fillvalue=unknown_symbol),
            partial(chain, [unknown_symbol] * align),
            partial(map, symbol)),
        availabilities)
    start_time = datetime(start_time.year, start_time.month, start_time.day, start_time.hour)
    for i, (seat_name, seat_availability) in enumerate(zip(names, availabilities)):
        if i % time_header_interval == 0:
            print(' ' * name_pad, end=' |')
            for time in range_generic(start_time, end_time, timedelta(hours=1)):
                print(time.strftime('%I%p'), end='|')
            print()
        print(seat_name, end=' |')
        for symbols in seat_availability:
            print(''.join(symbols), end='|')
        print()

def main():
    print('Get library metadata...')
    account_info = api_get_account_info()
    print('Found library branches:')
    branch_ids, branch_names = json_get_available_branch_props(account_info)
    print_branches(branch_ids, branch_names)
    branch_id = int(input('Select a library branch ID: '))
    tomorrow = False
    if datetime.now().hour >= 12:
        tomorrow = input('Seat availability for tomorrow is available. Retrieve them instead? (y/n): ')
        tomorrow = True if tomorrow.lower() == 'y' else False
    print('Getting seat availabilities...')
    start_time, end_time, seat_availabilities = get_seat_availabilities_today(account_info, branch_id, tomorrow=tomorrow)
    print(f'Display seat availabilities (for {"tomorrow" if tomorrow else "today"}):')
    print_seat_availabilities(start_time, end_time, seat_availabilities)

if __name__ == '__main__':
    main()