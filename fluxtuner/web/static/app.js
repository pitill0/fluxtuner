const statusNode = document.querySelector("[data-status]");
const healthButton = document.querySelector("[data-health-check]");

async function checkHealth() {
  if (!statusNode) return;

  statusNode.textContent = "Checking server...";

  try {
    const response = await fetch("/api/health", {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    statusNode.textContent = JSON.stringify(payload, null, 2);
  } catch (error) {
    statusNode.textContent = `Server check failed: ${error}`;
  }
}

if (healthButton) {
  healthButton.addEventListener("click", checkHealth);
}
