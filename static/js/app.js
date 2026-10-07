(() => {
  const menuButton = document.querySelector("[data-menu-toggle]");
  const sidebar = document.getElementById("sidebar");
  if (menuButton && sidebar) {
    menuButton.addEventListener("click", () => {
      const open = sidebar.classList.toggle("open");
      menuButton.setAttribute("aria-expanded", String(open));
    });
    document.addEventListener("click", (event) => {
      if (window.innerWidth <= 900 && sidebar.classList.contains("open") &&
          !sidebar.contains(event.target) && !menuButton.contains(event.target)) {
        sidebar.classList.remove("open");
        menuButton.setAttribute("aria-expanded", "false");
      }
    });
  }

  document.querySelectorAll("form[data-disable-on-submit]").forEach((form) => {
    form.addEventListener("submit", () => {
      const submit = form.querySelector('button[type="submit"], input[type="submit"]');
      if (submit) {
        submit.disabled = true;
        if (submit.tagName === "BUTTON") {
          submit.dataset.originalText = submit.textContent;
          submit.textContent = "Processing…";
        }
      }
    });
  });
})();
