const state = {
  charts: {},
  activities: [],
};

function formatDateInput(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function defaultRange() {
  const end = new Date();
  const start = new Date(end);
  start.setDate(start.getDate() - 13);
  return { start: formatDateInput(start), end: formatDateInput(end) };
}

function minutesToHoursText(seconds) {
  if (seconds == null) return "-";
  return `${(seconds / 3600).toFixed(2)} h`;
}

async function getJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${text}`);
  }
  return response.json();
}

function upsertChart(key, canvasId, config) {
  const canvas = document.getElementById(canvasId);
  if (state.charts[key]) {
    state.charts[key].destroy();
  }
  state.charts[key] = new Chart(canvas, config);
}

function renderOverview(summary) {
  document.getElementById("kpi-resting").textContent = summary.avg_resting_heart_rate ?? "-";
  document.getElementById("kpi-daily-hr").textContent = summary.avg_daily_heart_rate ?? "-";
  document.getElementById("kpi-stress").textContent = summary.avg_stress_level ?? "-";
  document.getElementById("kpi-sleep").textContent = minutesToHoursText(summary.avg_sleep_seconds);
}

function renderHeartRate(days) {
  upsertChart("heartRate", "heart-rate-chart", {
    type: "line",
    data: {
      labels: days.map((row) => row.calendar_date),
      datasets: [
        {
          label: "Resting HR",
          data: days.map((row) => row.resting_heart_rate),
          borderColor: "#b55d36",
          backgroundColor: "rgba(181, 93, 54, 0.12)",
          tension: 0.25,
        },
        {
          label: "Average HR",
          data: days.map((row) => row.average_heart_rate),
          borderColor: "#3f7a83",
          backgroundColor: "rgba(63, 122, 131, 0.12)",
          tension: 0.25,
        },
        {
          label: "Max HR",
          data: days.map((row) => row.max_heart_rate),
          borderColor: "#c7a227",
          backgroundColor: "rgba(199, 162, 39, 0.12)",
          tension: 0.25,
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      responsive: true,
    },
  });
}

function renderStress(days) {
  upsertChart("stress", "stress-chart", {
    type: "line",
    data: {
      labels: days.map((row) => row.calendar_date),
      datasets: [
        {
          label: "Average Stress",
          data: days.map((row) => row.average_stress_level),
          borderColor: "#6b4f8d",
          backgroundColor: "rgba(107, 79, 141, 0.12)",
          tension: 0.25,
        },
        {
          label: "Max Stress",
          data: days.map((row) => row.max_stress_level),
          borderColor: "#293b5f",
          backgroundColor: "rgba(41, 59, 95, 0.12)",
          tension: 0.25,
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      responsive: true,
    },
  });
}

function renderSleep(days) {
  upsertChart("sleep", "sleep-chart", {
    type: "bar",
    data: {
      labels: days.map((row) => row.sleep_date),
      datasets: [
        {
          label: "Sleep Hours",
          data: days.map((row) => row.total_sleep_seconds == null ? null : row.total_sleep_seconds / 3600),
          backgroundColor: "rgba(63, 122, 131, 0.72)",
          yAxisID: "y",
        },
        {
          label: "Sleep Score",
          data: days.map((row) => row.sleep_score),
          borderColor: "#c7a227",
          backgroundColor: "rgba(199, 162, 39, 0.2)",
          type: "line",
          yAxisID: "y1",
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      responsive: true,
      scales: {
        y: { position: "left" },
        y1: { position: "right", grid: { drawOnChartArea: false } },
      },
    },
  });
}

function renderHourly(hours) {
  upsertChart("hourly", "hourly-chart", {
    type: "bar",
    data: {
      labels: hours.map((row) => `${String(row.hour).padStart(2, "0")}:00`),
      datasets: [
        {
          label: "Average BPM",
          data: hours.map((row) => row.average_bpm),
          backgroundColor: "rgba(63, 122, 131, 0.72)",
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      responsive: true,
    },
  });
}

function populateActivities(activities) {
  state.activities = activities;
  const select = document.getElementById("activity-select");
  select.innerHTML = "";
  if (!activities.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "활동 데이터 없음";
    select.appendChild(option);
    renderActivity([]);
    return;
  }

  for (const activity of activities) {
    const option = document.createElement("option");
    option.value = activity.activity_id;
    option.textContent = `${activity.calendar_date} · ${activity.activity_name || "Unnamed"} · ${activity.activity_type || "unknown"}`;
    select.appendChild(option);
  }
}

function renderActivity(samples) {
  upsertChart("activity", "activity-chart", {
    type: "line",
    data: {
      labels: samples.map((row) => row.timestamp_local.slice(11, 19)),
      datasets: [
        {
          label: "Activity HR",
          data: samples.map((row) => row.bpm),
          borderColor: "#b55d36",
          backgroundColor: "rgba(181, 93, 54, 0.12)",
          pointRadius: 0,
          tension: 0.15,
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      responsive: true,
    },
  });
}

async function loadActivityDetail(activityId) {
  if (!activityId) {
    renderActivity([]);
    return;
  }
  const payload = await getJson(`/api/dashboard/activities/${activityId}/heart-rate`);
  renderActivity(payload.samples);
}

async function loadDashboard() {
  const start = document.getElementById("start-date").value;
  const end = document.getElementById("end-date").value;
  const query = `start=${start}&end=${end}`;

  const [overview, dailyHr, hourly, stress, sleep, activities, jobs] = await Promise.all([
    getJson(`/api/dashboard/overview?${query}`),
    getJson(`/api/dashboard/heart-rate/daily?${query}`),
    getJson(`/api/dashboard/heart-rate/hourly?${query}`),
    getJson(`/api/dashboard/stress/daily?${query}`),
    getJson(`/api/dashboard/sleep/daily?${query}`),
    getJson(`/api/dashboard/activities?${query}`),
    getJson(`/api/sync/jobs`),
  ]);

  renderOverview(overview.summary);
  renderHeartRate(dailyHr.days);
  renderStress(stress.days);
  renderSleep(sleep.days);
  renderHourly(hourly.hours);
  populateActivities(activities.activities);

  document.getElementById("sync-status").textContent = JSON.stringify(jobs.jobs, null, 2);
  if (activities.activities.length) {
    await loadActivityDetail(activities.activities[activities.activities.length - 1].activity_id);
  } else {
    renderActivity([]);
  }
}

async function triggerSync() {
  const button = document.getElementById("sync-button");
  button.disabled = true;
  button.textContent = "갱신 중...";
  try {
    await getJson("/api/sync/garmin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ days: 1 }),
    });
    await loadDashboard();
  } finally {
    button.disabled = false;
    button.textContent = "지금 갱신";
  }
}

function bindEvents() {
  document.getElementById("load-button").addEventListener("click", () => {
    loadDashboard().catch((error) => {
      alert(error.message);
    });
  });

  document.getElementById("sync-button").addEventListener("click", () => {
    triggerSync().catch((error) => {
      alert(error.message);
    });
  });

  document.getElementById("activity-select").addEventListener("change", (event) => {
    loadActivityDetail(event.target.value).catch((error) => {
      alert(error.message);
    });
  });
}

function setDefaultRange() {
  const range = defaultRange();
  document.getElementById("start-date").value = range.start;
  document.getElementById("end-date").value = range.end;
}

setDefaultRange();
bindEvents();
loadDashboard().catch((error) => {
  document.getElementById("sync-status").textContent = error.message;
});
