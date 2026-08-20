// DEMO LOGIN — front-end only.
//
// There is no user account database or authentication server behind this
// form. It exists to demonstrate the UI flow (Farmer / Researcher /
// Administrator roles), including role-based feature visibility on the
// calculator page. Submitting simply stores the chosen role in
// sessionStorage and redirects to the home page — it does NOT verify
// credentials or provide real security. Wiring this up to a real
// user/auth system is listed as future work.

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("login-form");
  const errorEl = document.getElementById("login-error");
  const submitBtn = document.getElementById("login-submit");

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    errorEl.hidden = true;

    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;
    const role = document.getElementById("role").value;

    if (!email || !password) {
      errorEl.textContent = "Please enter both email and password.";
      errorEl.hidden = false;
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Logging in\u2026";

    setTimeout(() => {
      sessionStorage.setItem("demoRole", role);
      sessionStorage.setItem("demoEmail", email);
      window.location.href = "/home";
    }, 500);
  });
});
