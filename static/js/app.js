
const districtSelect = document.getElementById('districtSelect');
const districtNameEl = document.getElementById('districtName');
const districtCodeEl = document.getElementById('districtCode');
const datasetLabelEl = document.getElementById('datasetLabel');
const chartTitleEl = document.getElementById('chartTitle');
const chartSubEl = document.getElementById('chartSub');
const tableEl = document.getElementById('dataTable');
const statusText = document.getElementById('statusText');
const chartCanvas = document.getElementById('chartCanvas');
const indexButtons = Array.from(document.querySelectorAll('.index-btn'));

let activeType = 'specialisation';
let chart = null;
let districts = [];
let config = {};

async function fetchJSON(url) {
  const response = await fetch(url);
  const text = await response.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error(text || 'Invalid server response');
  }
  if (!response.ok) {
    throw new Error(data.detail || 'Request failed');
  }
  return data;
}

function hexToRgba(hex, alpha) {
  const value = hex.replace('#', '');
  const bigint = parseInt(value, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function formatValue(value) {
  return activeType === 'productivity' ? Number(value).toFixed(2) : Number(value).toFixed(4);
}

async function loadConfig() {
  const data = await fetchJSON('/api/config');
  config = data.datasets;
}

async function loadDistricts() {
  const data = await fetchJSON('/api/districts');
  districts = data.districts;
  districtSelect.innerHTML = districts.map(item => (
    `<option value="${item.district_code}">${item.district_name}</option>`
  )).join('');
  statusText.textContent = `Loaded ${districts.length} districts from CSV files.`;
  const pune = districts.find(x => x.district_code === 2725);
  districtSelect.value = pune ? String(pune.district_code) : districtSelect.value;
  await loadDistrictData();
}

async function loadDistrictData() {
  const code = districtSelect.value;
  const dataset = config[activeType];
  statusText.textContent = `Loading ${dataset.label}...`;
  const data = await fetchJSON(`/api/district-data?district_code=${code}&dataset_type=${activeType}`);
  districtNameEl.textContent = data.district_name;
  districtCodeEl.textContent = data.district_code;
  datasetLabelEl.textContent = data.dataset_label;
  chartTitleEl.textContent = `Top 10 Industries — ${data.dataset_label}`;
  chartSubEl.textContent = `Ranked industries for ${data.district_name}.`;
  renderChart(data);
  renderTable(data);
  statusText.textContent = `${data.district_name} loaded from ${data.dataset_label}.`;
}

function renderChart(data) {
  const color = data.color;
  const labels = [...data.top_10.map(item => item.nic3_name)].reverse();
  const values = [...data.top_10.map(item => item.value)].reverse();
  if (chart) chart.destroy();
  chart = new Chart(chartCanvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: values.map((_, i) => hexToRgba(color, 0.35 + i * 0.05)),
        borderColor: values.map(() => hexToRgba(color, 0.95)),
        borderWidth: 1,
        borderRadius: 8,
        borderSkipped: false
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(8,16,30,0.94)',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          callbacks: {
            label: ctx => ` ${formatValue(ctx.raw)}`
          }
        }
      },
      scales: {
        x: {
          ticks: { color: '#9eb4cb' },
          grid: { color: 'rgba(255,255,255,0.06)' }
        },
        y: {
          ticks: { color: '#e7f0fb', font: { size: 11 } },
          grid: { display: false }
        }
      }
    }
  });
}

function renderTable(data) {
  const rows = data.top_10.map(row => `
    <tr>
      <td><span class="rank-pill">${row.rank}</span></td>
      <td>
        <div class="industry-name">${row.nic3_name}</div>
        <div class="subtle">NIC3: ${row.nic3_code}</div>
      </td>
      <td><span class="value-pill">${formatValue(row.value)}</span></td>
    </tr>
  `).join('');

  tableEl.innerHTML = `
    <thead>
      <tr>
        <th>Rank</th>
        <th>Industry</th>
        <th>Value</th>
      </tr>
    </thead>
    <tbody>${rows}</tbody>
  `;
}

function activateButton(type) {
  indexButtons.forEach(btn => {
    btn.classList.remove('active');
    if (btn.dataset.type === type) btn.classList.add('active');
  });
}

indexButtons.forEach(btn => {
  btn.addEventListener('click', async () => {
    activeType = btn.dataset.type;
    activateButton(activeType);
    await loadDistrictData();
  });
});

districtSelect.addEventListener('change', loadDistrictData);

(async function init() {
  try {
    await loadConfig();
    await loadDistricts();
  } catch (error) {
    console.error(error);
    statusText.textContent = error.message || 'Failed to load application data.';
  }
})();
