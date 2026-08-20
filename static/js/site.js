document.addEventListener("DOMContentLoaded", () => {
  const requiresAuth = document.body.dataset.requiresAuth === "true";
  if (requiresAuth && !sessionStorage.getItem("demoRole")) {
    window.location.href = "/";
    return;
  }

  const toggle = document.getElementById("nav-toggle");
  const links = document.getElementById("nav-links");
  if (toggle && links) {
    toggle.addEventListener("click", () => {
      const isOpen = links.classList.toggle("open");
      toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });
  }

  const loginLink = document.getElementById("nav-login-link");
  if (loginLink) {
    const role = sessionStorage.getItem("demoRole");
    if (role) {
      loginLink.textContent = `Log Out (${role})`;
      loginLink.addEventListener("click", (e) => {
        e.preventDefault();
        sessionStorage.removeItem("demoRole");
        sessionStorage.removeItem("demoEmail");
        window.location.href = "/";
      });
    }
  }
});
