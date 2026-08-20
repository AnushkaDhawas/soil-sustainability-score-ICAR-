const API_BASE = "";

const tabButtons = document.querySelectorAll(".tab-btn");
const tabPanels = document.querySelectorAll(".tab-panel");
const manualForm = document.getElementById("manual-form");
const locationForm = document.getElementById("location-form");
const resultPanel = document.getElementById("result-panel");
const locationResultsPanel = document.getElementById("location-results");
const locationResultsList = document.getElementById("location-results-list");
const formError = document.getElementById("form-error");
const roleBadge = document.getElementById("role-badge");
const roleNotice = document.getElementById("role-notice");
const manualTabBtn = document.getElementById("manual-tab-btn");

// --- Role-based access control ---
// Farmers only get village lookup (simpler, no lab-data entry required).
// Researchers and Administrators get both manual entry and village lookup.
// NOTE: this is a front-end UI gate tied to the demo login's sessionStorage
// role — it is not enforced by the API itself, consistent with the rest
// of the demo login system (see login.js for full disclosure).
function applyRoleAccess() {
  const role = sessionStorage.getItem("demoRole");

  if (role) {
    roleBadge.textContent = `Logged in as: ${role}`;
    roleBadge.hidden = false;
  }

  if (role === "Farmer") {
    manualTabBtn.style.display = "none";

    // Force the location tab to be the active (only) one.
    tabButtons.forEach((b) => { b.classList.remove("active"); b.setAttribute("aria-selected", "false"); });
    const locationTabBtn = document.querySelector('.tab-btn[data-tab="location"]');
    locationTabBtn.classList.add("active");
    locationTabBtn.setAttribute("aria-selected", "true");

    tabPanels.forEach((panel) => {
      panel.classList.toggle("active", panel.dataset.panel === "location");
    });

    roleNotice.textContent = "As a Farmer, you can look up your soil sustainability score by village. Manual lab-value entry is available to Researcher and Administrator accounts.";
    roleNotice.hidden = false;
  }
}
applyRoleAccess();

function showError(message) {
  formError.textContent = message;
  formError.hidden = false;
}
function clearError() {
  formError.hidden = true;
  formError.textContent = "";
}

tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.style.display === "none") return; // guard against hidden tab activation

    tabButtons.forEach((b) => { b.classList.remove("active"); b.setAttribute("aria-selected", "false"); });
    btn.classList.add("active");
    btn.setAttribute("aria-selected", "true");

    const targetTab = btn.dataset.tab;
    tabPanels.forEach((panel) => {
      panel.classList.toggle("active", panel.dataset.panel === targetTab);
    });

    resultPanel.hidden = true;
    locationResultsPanel.hidden = true;
    clearError();
  });
});

function categoryClass(category) {
  const map = {
    "Highly Sustainable": "cat-highly",
    "Moderately Sustainable": "cat-moderately",
    "Needs Improvement": "cat-needs",
    "Unsustainable": "cat-unsustainable",
  };
  return map[category] || "cat-moderately";
}

function renderScoreResult(data) {
  resultPanel.hidden = false;
  resultPanel.className = "panel result-panel " + categoryClass(data.category);

  document.getElementById("score-number").textContent = data.sss;
  document.getElementById("score-category").textContent = data.category;
  document.getElementById("chem-score").textContent = data.chemical_health_score;
  document.getElementById("phys-score").textContent = data.physical_health_score;

  resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

manualForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearError();
  resultPanel.hidden = true;
  locationResultsPanel.hidden = true;

  const formData = new FormData(manualForm);
  const payload = {
    ph: parseFloat(formData.get("ph")),
    ec: parseFloat(formData.get("ec")),
    organic_carbon: parseFloat(formData.get("organic_carbon")),
    nitrogen: parseFloat(formData.get("nitrogen")),
    phosphorus: parseFloat(formData.get("phosphorus")),
    potassium: parseFloat(formData.get("potassium")),
    texture_score: parseFloat(formData.get("texture")),
  };

  try {
    const res = await fetch(`${API_BASE}/score`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (!res.ok) {
      showError(data.error || "Something went wrong calculating the score.");
      return;
    }
    renderScoreResult(data);
  } catch (err) {
    showError("Could not reach the scoring service. Is the Flask app running?");
  }
});

locationForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearError();
  resultPanel.hidden = true;
  locationResultsPanel.hidden = true;

  const formData = new FormData(locationForm);
  const payload = {};
  ["state", "district", "block", "village"].forEach((key) => {
    const value = formData.get(key);
    if (value && value.trim() !== "") payload[key] = value.trim();
  });

  if (Object.keys(payload).length === 0) {
    showError("Enter at least one location field (state, district, block, or village).");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/score-by-location`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (!res.ok) {
      showError(data.error || "No matching soil profiles found for that location.");
      return;
    }

    renderLocationResults(data.profiles);
  } catch (err) {
    showError("Could not reach the lookup service. Is the Flask app running?");
  }
});

function renderLocationResults(profiles) {
  locationResultsPanel.hidden = false;
  locationResultsList.innerHTML = "";

  profiles.forEach((profile) => {
    const card = document.createElement("div");
    card.className = "profile-card";
    card.innerHTML = `
      <div>
        <div class="village-name">${profile.Village || "Unknown village"}</div>
        <div style="font-size:0.82rem;color:var(--ink-soft);">${profile.category}</div>
      </div>
      <div class="profile-score">${profile.sss}</div>
    `;
    locationResultsList.appendChild(card);
  });

  locationResultsPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}
