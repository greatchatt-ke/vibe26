// Mobile navigation toggle
const toggle = document.querySelector(".nav-toggle");
const menu = document.getElementById("nav-menu");

toggle.addEventListener("click", () => {
  const open = menu.classList.toggle("open");
  toggle.setAttribute("aria-expanded", String(open));
  toggle.setAttribute("aria-label", open ? "메뉴 닫기" : "메뉴 열기");
});

menu.addEventListener("click", (event) => {
  if (event.target.tagName === "A") {
    menu.classList.remove("open");
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "메뉴 열기");
  }
});

// Highlight the menu item of the section currently in view
const navLinks = [...menu.querySelectorAll("a")];
const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      navLinks.forEach((link) => {
        link.classList.toggle("active", link.getAttribute("href") === `#${entry.target.id}`);
      });
    });
  },
  { rootMargin: "-45% 0px -50% 0px" }
);
navLinks.forEach((link) => {
  const section = document.querySelector(link.getAttribute("href"));
  if (section) observer.observe(section);
});

// Projects are kept in data/projects.json so they can be edited without touching HTML
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function renderProject(project) {
  const tags = project.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join("");
  const links = [
    project.github && `<a href="${encodeURI(project.github)}" target="_blank" rel="noopener">GitHub</a>`,
    project.demo && `<a href="${encodeURI(project.demo)}" target="_blank" rel="noopener">Demo</a>`,
  ]
    .filter(Boolean)
    .join("");

  return `
    <article class="project-card">
      <h3>${escapeHtml(project.title)}</h3>
      <p>${escapeHtml(project.description)}</p>
      <ul class="tags">${tags}</ul>
      <div class="project-links">${links}</div>
    </article>`;
}

async function loadProjects() {
  const list = document.getElementById("projects-list");
  try {
    const response = await fetch("data/projects.json");
    if (!response.ok) throw new Error(response.statusText);
    const projects = await response.json();
    list.innerHTML = projects.map(renderProject).join("");
  } catch (error) {
    list.innerHTML = '<p class="muted">프로젝트를 불러오지 못했습니다. 로컬 서버로 실행해 주세요.</p>';
  }
}

loadProjects();

// Copy email address
const copyButton = document.getElementById("copy-email");
const copyStatus = document.getElementById("copy-status");

copyButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(copyButton.dataset.email);
    copyStatus.textContent = "이메일 주소를 복사했습니다.";
  } catch (error) {
    copyStatus.textContent = `복사하지 못했습니다: ${copyButton.dataset.email}`;
  }
  setTimeout(() => (copyStatus.textContent = ""), 2500);
});

document.getElementById("year").textContent = new Date().getFullYear();
