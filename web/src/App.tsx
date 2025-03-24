import { useState, useEffect } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  useNavigate,
  useParams,
} from "react-router-dom";
import "./App.css";

// Types
interface Library {
  id: number;
  name: string;
  current_capacity: number;
  total_capacity: number;
}

interface LibraryData {
  [date: string]: Library[];
}

// Types for seating data
interface Seat {
  [seatId: string]: boolean[];
}

interface AreaSeating {
  area: string;
  start_time: string;
  end_time: string;
  seats: Seat;
}

// const BASE_URL = "http://127.0.0.1:8000";
const BASE_URL = "https://lczm.me/nlb-seatings";

// Library Detail Page
function LibraryDetail() {
  const { date, id } = useParams();
  const navigate = useNavigate();
  const [library, setLibrary] = useState<Library | null>(null);
  const [loading, setLoading] = useState(true);
  const [, setLibraryData] = useState<LibraryData>({});
  const [seatingData, setSeatingData] = useState<AreaSeating[]>([]);
  const [loadingSeats, setLoadingSeats] = useState(false);
  const [selectedArea, setSelectedArea] = useState<string>("");

  useEffect(() => {
    // Fetch the library data
    fetch(`${BASE_URL}/branches`)
      .then((response) => response.json())
      .then((data: LibraryData) => {
        setLibraryData(data);
        setLoading(false);

        // Find the specific library
        if (date && id && data[date]) {
          const lib = data[date].find((lib) => lib.id === parseInt(id));
          if (lib) {
            setLibrary(lib);

            // Now fetch seating data
            setLoadingSeats(true);
            fetch(`${BASE_URL}/seatings/${date}/${id}`)
              .then((response) => response.json())
              .then((seatData: AreaSeating[]) => {
                setSeatingData(seatData);
                if (seatData.length > 0) {
                  setSelectedArea(seatData[0].area);
                }
                setLoadingSeats(false);
              })
              .catch((error) => {
                console.error("Error fetching seating data:", error);
                setLoadingSeats(false);
              });
          }
        }
      })
      .catch((error) => {
        console.error("Error fetching library data:", error);
        setLoading(false);
      });
  }, [date, id]);

  // Function to format time for column headers (just the hour)
  const formatHourHeader = (date: Date) => {
    return date.toLocaleTimeString("en-US", {
      hour: "numeric",
      hour12: true,
    });
  };

  // Function to render timetable-style seat availability
  const renderSeatAvailabilityTable = (areaData: AreaSeating) => {
    if (
      !areaData ||
      !areaData.seats ||
      Object.keys(areaData.seats).length === 0
    )
      return null;

    const startTime = new Date(areaData.start_time);
    const endTime = new Date(areaData.end_time);

    // Number of time slots based on the first seat's availability array
    const firstSeatId = Object.keys(areaData.seats)[0];
    const totalTimeSlots = areaData.seats[firstSeatId].length;

    if (totalTimeSlots === 0) return null;

    // Calculate time increment for each slot
    const totalTimeMs = endTime.getTime() - startTime.getTime();
    const timePerSlotMs = totalTimeMs / totalTimeSlots;

    // Generate time slot headers
    const timeSlotHeaders = [];
    for (let i = 0; i < totalTimeSlots; i++) {
      const slotTime = new Date(startTime.getTime() + i * timePerSlotMs);
      timeSlotHeaders.push(formatHourHeader(slotTime));
    }

    // Group time slots into hour blocks (for better display)
    const groupedTimeSlots: { [hour: string]: number[] } = {};

    timeSlotHeaders.forEach((hour, index) => {
      if (!groupedTimeSlots[hour]) {
        groupedTimeSlots[hour] = [];
      }
      groupedTimeSlots[hour].push(index);
    });

    // Get unique hours in order
    const uniqueHours = Object.keys(groupedTimeSlots);

    return (
      <div className="overflow-x-auto mt-4 font-mono text-sm">
        <table className="min-w-full border-collapse">
          <thead>
            <tr>
              <th className="p-2 text-left w-16 min-w-fit whitespace-nowrap">
                Seat
              </th>
              {uniqueHours.map((hour) => (
                <th key={hour} className="p-2 text-center">
                  {hour}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.entries(areaData.seats).map(([seatId, availability]) => (
              <tr key={seatId} className="hover:bg-gray-50">
                <td className="p-2 font-medium w-16 min-w-fit whitespace-nowrap">
                  {seatId}
                </td>

                {uniqueHours.map((hour, hourIdx) => {
                  const slotIndexes = groupedTimeSlots[hour];
                  return (
                    <td key={hourIdx} className="p-2 text-center">
                      <div className="flex justify-center items-center space-x-0">
                        {slotIndexes.map((idx) => (
                          <div
                            key={idx}
                            className={`w-2 h-6 ${
                              availability[idx] ? "bg-green-400" : "bg-red-500"
                            }`}
                            title={`${seatId} at ${hour}: ${
                              availability[idx] ? "Available" : "Unavailable"
                            }`}
                          ></div>
                        ))}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-xl font-semibold">Loading...</div>
      </div>
    );
  }

  if (!library) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <button
          className="mb-4 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          onClick={() => navigate("/nlb-seatings")}
        >
          Back to Libraries
        </button>
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          Library not found
        </div>
      </div>
    );
  }

  // Find the currently selected area data
  const currentAreaData = seatingData.find(
    (area) => area.area === selectedArea
  );

  const occupancyRate =
    ((library.total_capacity - library.current_capacity) /
      library.total_capacity) *
    100;

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <button
        className="mb-4 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        onClick={() => navigate("/nlb-seatings")}
      >
        Back to Libraries
      </button>

      <div className="bg-white shadow-lg rounded-lg overflow-hidden mb-6">
        <div className="bg-blue-500 text-white p-4">
          <h1 className="text-2xl font-bold">{library.name}</h1>
          <p className="text-sm">Date: {date}</p>
        </div>

        <div className="p-6">
          <div className="mb-4">
            <h2 className="text-lg font-semibold mb-2">Capacity Information</h2>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-100 p-4 rounded">
                <p className="text-sm text-gray-500">Current Capacity</p>
                <p className="text-2xl font-bold">{library.current_capacity}</p>
              </div>
              <div className="bg-gray-100 p-4 rounded">
                <p className="text-sm text-gray-500">Total Capacity</p>
                <p className="text-2xl font-bold">{library.total_capacity}</p>
              </div>
            </div>
          </div>

          <div className="mb-4">
            <h2 className="text-lg font-semibold mb-2">Occupancy Rate</h2>
            <div className="w-full bg-gray-200 rounded-full h-4">
              <div
                className="bg-blue-600 h-4 rounded-full"
                style={{
                  width: `${occupancyRate}%`,
                }}
              ></div>
            </div>
            <p className="text-right text-sm mt-1">
              {Math.round(occupancyRate)}%
            </p>
          </div>
        </div>
      </div>

      {/* Seating Availability Section */}
      <div className="bg-white shadow-lg rounded-lg overflow-hidden">
        <div className="bg-blue-500 text-white p-4">
          <h2 className="text-xl font-bold">Seating Availability</h2>
        </div>

        <div className="p-6">
          {loadingSeats ? (
            <div className="flex justify-center items-center h-40">
              <div className="text-lg">Loading seat information...</div>
            </div>
          ) : seatingData.length === 0 ? (
            <div className="bg-yellow-100 border border-yellow-400 text-yellow-700 px-4 py-3 rounded">
              No seating information available for this library.
            </div>
          ) : (
            <>
              {/* Area Tabs */}
              <div className="border-b mb-6">
                <div className="flex flex-wrap">
                  {seatingData.map((area) => (
                    <button
                      key={area.area}
                      className={`py-2 px-4 font-medium ${
                        selectedArea === area.area
                          ? "border-b-2 border-blue-500 text-blue-500"
                          : "text-gray-500 hover:text-gray-700"
                      }`}
                      onClick={() => setSelectedArea(area.area)}
                    >
                      {area.area}
                    </button>
                  ))}
                </div>
              </div>

              {/* Legend */}
              <div className="flex mb-4 text-sm">
                <div className="flex items-center mr-4">
                  <div className="w-4 h-4 bg-green-500 rounded mr-1"></div>
                  <span>Available</span>
                </div>
                <div className="flex items-center">
                  <div className="w-4 h-4 bg-red-500 rounded mr-1"></div>
                  <span>Unavailable</span>
                </div>
              </div>

              {/* Seat Availability Timetable */}
              {currentAreaData && renderSeatAvailabilityTable(currentAreaData)}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// Library Card Component
function LibraryCard({
  library,
  onClick,
}: {
  library: Library;
  date: string;
  onClick: () => void;
}) {
  const occupancyRate =
    ((library.total_capacity - library.current_capacity) /
      library.total_capacity) *
    100;

  // Determine color based on occupancy rate
  let statusColor = "bg-green-500";
  if (occupancyRate > 80) statusColor = "bg-red-500";
  else if (occupancyRate > 50) statusColor = "bg-yellow-500";

  return (
    <div
      className="bg-white rounded-lg shadow-md overflow-hidden cursor-pointer transform transition hover:scale-105"
      onClick={onClick}
    >
      <div className={`${statusColor} h-2 w-full`}></div>
      <div className="p-4">
        <h3 className="font-bold text-lg mb-2">{library.name}</h3>
        <div className="flex justify-between text-sm text-gray-600 mb-2">
          <span>Current: {library.current_capacity} units</span>
          <span>Total: {library.total_capacity} units</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className={`${statusColor} h-2 rounded-full`}
            style={{ width: `${occupancyRate}%` }}
          ></div>
        </div>
        <div className="text-right text-xs mt-1">
          {Math.round(occupancyRate)}% Occupied
        </div>
      </div>
    </div>
  );
}

// Home Page Component
function Home() {
  const [libraryData, setLibraryData] = useState<LibraryData>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>("");
  const navigate = useNavigate();

  useEffect(() => {
    // Fetch library data when component mounts
    fetch(`${BASE_URL}/branches`)
      .then((response) => {
        if (!response.ok) {
          throw new Error("Network response was not ok");
        }
        return response.json();
      })
      .then((data: LibraryData) => {
        setLibraryData(data);

        // Set active tab to the first date
        if (Object.keys(data).length > 0) {
          setActiveTab(Object.keys(data)[0]);
        }

        setLoading(false);
      })
      .catch((error) => {
        console.error("Error fetching library data:", error);
        setError("Failed to load library data. Please try again later.");
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-xl font-semibold">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      </div>
    );
  }

  const dates = Object.keys(libraryData);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">NLB Seat Availabilities</h1>

      {/* Tabs */}
      <div className="border-b mb-6">
        <div className="flex">
          {dates.map((date) => (
            <button
              key={date}
              className={`py-2 px-4 font-medium ${
                activeTab === date
                  ? "border-b-2 border-blue-500 text-blue-500"
                  : "text-gray-500 hover:text-gray-700"
              }`}
              onClick={() => setActiveTab(date)}
            >
              {new Date(date).toLocaleDateString("en-US", {
                weekday: "short",
                month: "short",
                day: "numeric",
              })}
            </button>
          ))}
        </div>
      </div>

      {/* Library Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {activeTab &&
          libraryData[activeTab]?.map((library) => (
            <LibraryCard
              key={library.id}
              library={library}
              date={activeTab}
              onClick={() =>
                navigate(`/nlb-seatings/${activeTab}/${library.id}`)
              }
            />
          ))}
      </div>
    </div>
  );
}

// Main App Component
function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/nlb-seatings/" element={<Home />} />
        <Route path="/nlb-seatings/:date/:id" element={<LibraryDetail />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
