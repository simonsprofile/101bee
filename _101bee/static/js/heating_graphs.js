// Collate elements to display graphs
const dailyChart = document.getElementById('dailyChart');
const weeklyChart = document.getElementById('weeklyChart');
const monthlyChart = document.getElementById('monthlyChart');
const yearlyChart = document.getElementById('yearlyChart');
var dataset_shortlist = []

// Create datasets from data
function addToShortlist(name, data, colour, hide) {
  console.log(data);
  var dataRecords = data.map(item => ({
    x: new Date(item.x),
    y: item.y
  }));
  dataset_shortlist.push({
    label: name,
    data: dataRecords,
    backgroundColor: 'transparent',
    borderColor: colour,
    borderWidth: 2,
    tension: 0.5,
    hidden: hide
  });
}
addToShortlist('Room Setpoint', roomSetpointRecordsJSON, '#9C5013', true);
addToShortlist('Tank Setpoint', tankSetpointRecordsJSON, 'darkblue', true);
addToShortlist('Flow', flowTemperatureRecordsJSON, '#204809', false);
addToShortlist('Return', returnTemperatureRecordsJSON, '#B7B863', false);

const cooler_room = 'rgb(0, 153, 0, 0.3)';
const colours = {
    'Hot Water': 'cornflowerblue',
    'Thermostat': '#D66F1A',
    'Outdoor': '#BAA9D2',
    'Plant Room': 'rgb(225, 179, 198, 0.7)',
    'Front Bedroom': cooler_room,
    'Back Bedroom': cooler_room,
    'Studio': cooler_room,
    'Bathroom': cooler_room,
    'Kitchen': cooler_room,
    'Toilet': cooler_room,
    'Hallway': cooler_room,
    'Landing': cooler_room,
};
const hide_these_datatsets = [
    'Hot Water',
    'Bathroom',
    'Hallway',
    'Landing',
    'Kitchen',
    'Outdoor',
    'Plant Room'
]

for (sensor_name in sensorRecords) {
    sensor_records = sensorRecords[sensor_name];
    var colour = 'rgb(214, 111, 26, 0.5)';
    if (sensor_name in colours) {
        colour = colours[sensor_name];
    }
    var hide_dataset = false;
    if (hide_these_datatsets.includes(sensor_name)) {
        hide_dataset = true;
    }
    addToShortlist(
      sensor_name,
      JSON.parse(sensor_records),
      colour,
      hide_dataset
    );
}

// Re-Order Datasets
var datasets = [];
var ordering = [
    'Room Setpoint',
    'Thermostat',
    'Kitchen',
    'Living Room'
    'Hallway',

    'Landing',
    'Bathroom',
    'Back Bedroom',
    'Front Bedroom',
    'Studio',

    'Tank Setpoint',
    'Hot Water',

    'Outdoor',
    'Plant Room',

    'Flow',
    'Return'
];
for (var s = 0; s < ordering.length; s++) {
    var search_for = ordering[s];
    for (var d = 0; d < dataset_shortlist.length; d++) {
        let dataset_name = dataset_shortlist[d].label;
        if (search_for == dataset_name) {
            datasets.push(dataset_shortlist.splice(d, 1)[0]);
        }
    }
}
datasets = datasets.concat(dataset_shortlist);

// Create Daily chart straight away.
new Chart(dailyChart, {
    type: 'line',
    data: {
      datasets: datasets
    },
    options: {
        scales: {
            x: {
              type: 'time',
              min: oneDayAgo,
              max: timeNow,
              time: {
                unit: 'hour',
                displayFormats: {
                    minute: 'HH:mm'
                }
              },
              ticks: {
                // Force ticks for all hours, even with missing data
                source: 'linear',  // Use 'linear' for consistent ticks
                major: {
                  unit: 'hour' // Display major ticks for each hour
                }
              },
              title: {
                display: true,
                text: 'Time'
              }
            },
            y: {
              type: 'logarithmic',
              title: {
                display: true,
                text: 'Temperature (ºC)'
              }
            }
        },
        plugins: {
            legend: {
                align: 'center',
                labels: {
                    padding: 15,
                    usePointStyle: true,
                    pointStyle: 'line'
                },
                title: {
                    display: true,
                    text: 'Legend',
                    font: {
                       size: 14,
                       weight: 'bold'
                    }
                }
            }
        },
        layout: {
            padding: {

            }
        }
    }
});


// Prep other graphs
function loadTwoDailyChart() {
  new Chart(twoDailyChart, {
      type: 'line',
      data: {
        datasets: datasets
      },
      options: {
        scales: {
          x: {
            type: 'time',
            min: twoDaysAgo,
            max: timeNow,
            time: {
              unit: 'hour',
              displayFormats: {
                  minute: 'HH:mm'
              }
            },
            ticks: {
              // Force ticks for all hours, even with missing data
              source: 'linear',  // Use 'linear' for consistent ticks
              major: {
                unit: 'hour' // Display major ticks for each hour
              }
            },
            title: {
              display: true,
              text: 'Time'
            }
          },
          y: {
            type: 'logarithmic',
            title: {
              display: true,
              text: 'Temperature (ºC)'
            }
          }
        }
      }
  });
}

function loadWeeklyChart() {
  new Chart(weeklyChart, {
      type: 'line',
      data: {
        datasets: datasets
      },
      options: {
        elements: {
          point:{
            radius: 0
          }
        },
        bezierCurve: true,
        scales: {
          x: {
            type: 'time',
            min: oneWeekAgo,
            max: timeNow,
            time: {
              unit: 'day',
              displayFormats: {
                  day: 'EEEE'
              }
            },
            ticks: {
              // Force ticks for all hours, even with missing data
              source: 'linear',  // Use 'linear' for consistent ticks
              major: {
                unit: 'hour' // Display major ticks for each hour
              }
            },
            title: {
              display: true,
              text: 'Time'
            }
          },
          y: {
            type: 'logarithmic',
            title: {
              display: true,
              text: 'Temperature (ºC)'
            }
          }
        }
      }
  });
}

function loadMonthlyChart() {
  new Chart(monthlyChart, {
      type: 'line',
      data: {
        datasets: datasets
      },
      options: {
        elements: {
          point:{
            radius: 0
          }
        },
        bezierCurve: true,
        scales: {
          x: {
            type: 'time',
            min: oneMonthAgo,
            max: timeNow,
            time: {
              unit: 'day',
              displayFormats: {
                  day: 'd MMM'
              }
            },
            ticks: {
              // Force ticks for all hours, even with missing data
              source: 'linear',  // Use 'linear' for consistent ticks
              major: {
                unit: 'hour' // Display major ticks for each hour
              }
            },
            title: {
              display: true,
              text: 'Time'
            }
          },
          y: {
            type: 'logarithmic',
            title: {
              display: true,
              text: 'Temperature (ºC)'
            }
          }
        }
      }
  });
}

function loadYearlyChart() {
  new Chart(yearlyChart, {
      type: 'line',
      data: {
        datasets: datasets
      },
      options: {
        elements: {
          point:{
            radius: 0
          }
        },
        bezierCurve: true,
        scales: {
          x: {
            type: 'time',
            min: oneYearAgo,
            max: timeNow,
            time: {
              unit: 'month',
              displayFormats: {
                  month: 'MMMM'
              }
            },
            ticks: {
              // Force ticks for all hours, even with missing data
              source: 'linear',  // Use 'linear' for consistent ticks
              major: {
                unit: 'hour' // Display major ticks for each hour
              }
            },
            title: {
              display: true,
              text: 'Time'
            }
          },
          y: {
            type: 'logarithmic',
            title: {
              display: true,
              text: 'Temperature (ºC)'
            }
          }
        }
      }
  });
}

function loadGraph(graph_name) {
    switch (graph_name) {
        case '48 Hour':
            loadTwoDailyChart();
            break;
        case 'Week':
            loadWeeklyChart();
            break;
        case 'Month':
            loadMonthlyChart();
            break;
        case 'Year':
            loadYearlyChart();
            break;
        default:
            // Handle invalid tab ID
            break;
    }
}

// Load graphs when tabs open
function showAndLoadTab(id, graph_name) {
  try {
    loadGraph(graph_name);
  } catch(err) {}
  showTab('tab', id);
}