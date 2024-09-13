        // Collate elements to display graphs
        const dailyChart = document.getElementById('dailyChart');
        const weeklyChart = document.getElementById('weeklyChart');
        const monthlyChart = document.getElementById('monthlyChart');
        const yearlyChart = document.getElementById('yearlyChart');
        var dataset_shortlist = []

        // Collate data from view
        const roomSetpointRecordsJSON = JSON.parse('{{ room_setpoint_records|safe }}');
        const tankSetpointRecordsJSON = JSON.parse('{{ tank_setpoint_records|safe }}');
        const flowTemperatureRecordsJSON = JSON.parse('{{ flow_temperature_records|safe }}');
        const returnTemperatureRecordsJSON = JSON.parse('{{ return_temperature_records|safe }}');

        // Create datasets from data
        function addToShortlist(name, data, colour, hide) {
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
        addToShortlist('Flow Temperature', flowTemperatureRecordsJSON, '#204809', false);
        addToShortlist('Flow Temperature', returnTemperatureRecordsJSON, '#B7B863', false);

        const colours = {
            'Hot Water': 'cornflowerblue',
            'Thermostat': '#D66F1A',
            'Outdoor': '#BAA9D2',
            'Plant Room': 'rgb(225, 179, 198, 0.8)'
        };
        const hide_these_datatsets = [
            'Hot Water'
        ]

        {% for sensor_name, sensor_records in sensor_records.items %}
            var colour = 'rgb(214, 111, 26, 0.3)';
            if ('{{ sensor_name|safe }}' in colours) {
                colour = colours['{{ sensor_name|safe }}'];
            }
            var hide_dataset = false;
            if (hide_these_datatsets.includes('{{ sensor_name|safe }}')) {
                hide_dataset = true;
            }
            const {{ sensor_name|cut:" "|safe }}JSON = JSON.parse('{{ sensor_records|safe }}');
            addToShortlist(
              '{{ sensor_name|safe }}', 
              {{ sensor_name|cut:" "|safe }}JSON,
              colour,
              hide_dataset
            );
        {% endfor %}

        // Re-Order Datasets
        var datasets = [];
        var ordering = [
            'Room Setpoint',
            'Thermostat',
            'Kitchen',
            'Landing',
            'Hallway',
            'Living Room',

            'Tank Setpoint',
            'Hot Water',

            'Outdoor',
            'Plant Room',

            'Flow Temperature',
            'Return Temperature'
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

        function showAndLoadTab(id, graph_name) {
          console.log('Show tab ' + graph_name);
          showTab('tab', id);
        }


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
                      min: '{{ one_day_ago }}',
                      max: '{{ now }}',
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