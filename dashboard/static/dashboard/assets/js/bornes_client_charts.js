document.addEventListener("DOMContentLoaded", function () {
  // Graph interactions par borne
  const interCtx = document.getElementById("interactionsChart").getContext("2d");
  new Chart(interCtx, {
    type: 'bar',
    data: {
      labels: borneLabels,
      datasets: [{
        label: 'Interactions',
        data: interactionData,
        backgroundColor: '#4e73df',
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false }
      }
    }
  });

  // Graph satisfaction par borne
  const satCtx = document.getElementById("satisfactionChart").getContext("2d");
  new Chart(satCtx, {
    type: 'bar',
    data: {
      labels: borneLabels,
      datasets: [{
        label: 'Satisfaction (%)',
        data: satisfactionData,
        backgroundColor: '#1cc88a',
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false }
      },
      scales: {
        y: {
          max: 100,
          min: 0,
          ticks: {
            callback: value => value + "%"
          }
        }
      }
    }
  });
});
