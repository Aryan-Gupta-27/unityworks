(function () {
  const root = document.documentElement;
  const saved = localStorage.getItem("uw-theme");
  if (saved) root.dataset.theme = saved;

  document.querySelectorAll(".theme-toggle").forEach((button) => {
    button.addEventListener("click", () => {
      root.dataset.theme = root.dataset.theme === "dusk" ? "night" : "dusk";
      localStorage.setItem("uw-theme", root.dataset.theme);
    });
  });

  document.querySelectorAll("[data-open-sidebar], .public-menu").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.classList.contains("public-menu")) {
        const links = document.querySelector(".public-links");
        if (links) links.classList.toggle("open");
        return;
      }
      document.body.classList.add("sidebar-open");
    });
  });
  document.querySelectorAll("[data-close-sidebar]").forEach((el) => {
    el.addEventListener("click", () => document.body.classList.remove("sidebar-open"));
  });

  document.querySelectorAll(".flash-close").forEach((button) => {
    button.addEventListener("click", () => button.parentElement.remove());
  });
  setTimeout(() => {
    document.querySelectorAll(".flash").forEach((flash) => flash.remove());
  }, 5600);

  document.querySelectorAll("[data-toggle-password]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = button.parentElement.querySelector("input");
      if (!input) return;
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      button.textContent = show ? "Hide" : "Show";
    });
  });

  document.querySelectorAll(".demo-fill").forEach((button) => {
    button.addEventListener("click", () => {
      const form = document.querySelector(".auth-card");
      if (!form) return;
      form.querySelector("[name=identifier]").value = button.dataset.ident;
      form.querySelector("[name=password]").value = button.dataset.password;
    });
  });

  const thread = document.getElementById("thread");
  if (thread && thread.dataset.conversation) {
    const bubbles = document.getElementById("bubbles");
    const token = document.querySelector('input[name="csrf_token"]');
    async function poll() {
      const after = thread.dataset.after || "0";
      try {
        const response = await fetch(`/messages/${thread.dataset.conversation}/updates?after=${after}&mark=1`);
        if (!response.ok) return;
        const data = await response.json();
        data.messages.forEach((message) => {
          if (document.querySelector(`[data-id="${message.id}"]`)) return;
          const article = document.createElement("article");
          article.className = "bubble" + (message.mine ? " mine" : "") + (message.deleted ? " deleted" : "");
          article.dataset.id = message.id;
          const header = document.createElement("header");
          header.textContent = `${message.sender} · ${message.created}`;
          const body = document.createElement("div");
          body.className = "rich";
          body.innerHTML = message.html;
          article.append(header, body);
          bubbles.append(article);
          thread.dataset.after = message.id;
        });
        const badge = document.querySelector(".nav-item .count");
        if (badge && typeof data.unread_messages === "number") {
          badge.textContent = data.unread_messages || "";
          if (!data.unread_messages) badge.remove();
        }
      } catch (err) {
        /* polling is an enhancement */
      }
    }
    setInterval(poll, 4000);
    if (token) thread.dataset.csrf = token.value;
  }
})();
