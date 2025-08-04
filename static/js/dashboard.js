document.addEventListener("DOMContentLoaded", function () {
  const table = document.getElementById("data-table");
  const summaryCards = document.getElementById("summary-cards");
  const chartCtx = document.getElementById("depositChart").getContext("2d");

  const startDate = document.getElementById("startDate");
  const endDate = document.getElementById("endDate");
  const orderBy = document.getElementById("orderBy");
  const orderDirection = document.getElementById("orderDirection");

  function fetchData() {
    const params = new URLSearchParams({
      startDate: new Date(startDate.value).toISOString(),
      endDate: new Date(endDate.value).toISOString(),
      orderBy: orderBy.value,
      orderDirection: orderDirection.value,
    });

    fetch(`/data?${params.toString()}`)
      .then(res => res.json())
      .then(data => {
        table.innerHTML = "";
        const amounts = [];

        data.data.forEach(d => {
          table.innerHTML += \`
            <tr>
              <td class="border px-4 py-2">\${d.user.name}</td>
              <td class="border px-4 py-2">\${d.user.email}</td>
              <td class="border px-4 py-2">R$ \${d.amount.toFixed(2)}</td>
              <td class="border px-4 py-2">\${new Date(d.createdAt).toLocaleString()}</td>
              <td class="border px-4 py-2">\${d.status}</td>
            </tr>\`;
          amounts.push({ date: d.createdAt, value: d.amount });
        });

        updateSummary(amounts);
        updateChart(amounts);
      });
  }

  function updateSummary(amounts) {
    const total = amounts.reduce((sum, a) => sum + a.value, 0);
    summaryCards.innerHTML = \`
      <div class="p-4 bg-blue-100 rounded shadow">
        <h2 class="text-xl font-semibold">Total Aprovado</h2>
        <p class="text-2xl mt-2 font-bold">R$ \${total.toFixed(2)}</p>
      </div>
    \`;
  }

  function updateChart(amounts) {
    const grouped = {};
    amounts.forEach(a => {
      const day = new Date(a.date).toLocaleDateString();
      grouped[day] = (grouped[day] || 0) + a.value;
    });

    const labels = Object.keys(grouped);
    const values = Object.values(grouped);

    new Chart(chartCtx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: 'Depósitos por dia',
          data: values,
          borderColor: 'blue',
          fill: false,
        }]
      }
    });
  }

  [startDate, endDate, orderBy, orderDirection].forEach(el => el.addEventListener("change", fetchData));

  // Valores iniciais
  const today = new Date().toISOString().split("T")[0];
  startDate.value = "2025-01-01";
  endDate.value = today;
  fetchData();
});
