"use strict";
let previousFocus;
document.querySelectorAll("dialog[open]").forEach(dialog => { if (dialog.dataset.returnFocus) previousFocus=document.getElementById(dialog.dataset.returnFocus); dialog.close(); dialog.showModal(); });
document.querySelectorAll("dialog[data-required]").forEach(dialog => dialog.addEventListener("cancel", event => event.preventDefault()));
document.querySelectorAll("dialog").forEach(dialog => dialog.addEventListener("keydown", event => {
  if (event.key !== "Tab") return;
  const controls = [...dialog.querySelectorAll('button:not(:disabled), a[href], input:not([type="hidden"]):not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]')].filter(element => element.getClientRects().length);
  const first = controls[0], last = controls.at(-1);
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
}));
document.querySelectorAll("[data-choose]").forEach(link => link.addEventListener("click", event => {
  event.preventDefault();
  previousFocus = link;
  document.getElementById("choice-name").textContent = link.dataset.name;
  document.getElementById("choice-form").action = link.href;
  document.getElementById("choice-modal").showModal();
}));
document.querySelectorAll("[data-cancel-manager]").forEach(button => button.addEventListener("click", event => {
  if (!window.confirm("Cancelar esta escolha e disponibilizar o presente novamente?")) event.preventDefault();
}));
document.querySelectorAll("[data-cancel-choice]").forEach(button => button.addEventListener("click", event => {
  if (!window.confirm("Cancelar a escolha deste presente? Suas outras escolhas serão mantidas.")) event.preventDefault();
}));
document.querySelectorAll("[data-open]").forEach(button => button.addEventListener("click", () => {
  previousFocus = button;
  document.getElementById(button.dataset.open).showModal();
}));
document.querySelectorAll("[data-close]").forEach(button => button.addEventListener("click", () => button.closest("dialog").close()));
document.querySelectorAll("[data-illustration-selector]").forEach(form => {
  const select = form.querySelector("select");
  const dialog = form.closest("dialog");
  select.addEventListener("change", () => {
    const changed = select.value !== form.dataset.previewChoice;
    const confirm = dialog.querySelector("[data-confirm-illustration]");
    if (confirm) confirm.disabled = changed;
    dialog.querySelector("[data-preview-needed]").hidden = !changed;
  });
});
document.querySelectorAll("dialog").forEach(dialog => dialog.addEventListener("close", () => previousFocus?.focus()));
document.querySelectorAll("img[data-fallback]").forEach(image => image.addEventListener("error", () => { image.src = image.dataset.fallback; delete image.dataset.fallback; }, {once:true}));
document.querySelectorAll("form[data-loading]").forEach(form => form.addEventListener("submit", () => {
  const button = form.querySelector('button[type="submit"]');
  if (button) { button.disabled = true; button.textContent = form.dataset.loading; }
  const status = form.querySelector(".form-status");
  if (status) status.textContent = "Salvando as alterações…";
  form.setAttribute("aria-busy", "true");
}));
const addLink = document.getElementById("add-link");
const fields = document.getElementById("link-fields");
const total = document.getElementById("id_links-TOTAL_FORMS");
function renumberLinks() {
  fields.querySelectorAll(".link-row").forEach((row, index) => {
    const input = row.querySelector("input");
    input.name = `links-${index}-url`;
    input.id = `id_links-${index}-url`;
    row.querySelector("label").htmlFor = input.id;
    row.querySelector("label").textContent = `Inserir link do anúncio${index ? ` ${index + 1}` : ""}`;
  });
  total.value = fields.children.length;
  addLink.disabled = fields.children.length >= 10;
}
addLink?.addEventListener("click", () => {
  if (fields.children.length >= 10) return;
  const html = document.getElementById("link-template").innerHTML.replaceAll("__prefix__", total.value);
  fields.insertAdjacentHTML("beforeend", html);
  renumberLinks();
  fields.lastElementChild.querySelector("input").focus();
});
fields?.addEventListener("click", event => {
  if (!event.target.matches(".remove-link")) return;
  event.target.closest(".link-row").remove();
  renumberLinks();
  addLink.focus();
});
window.addEventListener("pageshow", () => document.querySelectorAll("form[data-loading]").forEach(form => {
  form.removeAttribute("aria-busy");
  const button = form.querySelector('button[type="submit"]');
  if (button && button.disabled) window.location.reload();
}));

(() => {
  const splash = document.getElementById("welcome-splash");
  if (!splash) return;
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let seen = false;
  try { seen = sessionStorage.getItem("presentes:splash-seen") === "1"; } catch {}
  const photo = splash.querySelector("img");
  if (seen || reducedMotion.matches || typeof splash.showModal !== "function" || (photo.complete && !photo.naturalWidth)) {
    splash.remove();
    return;
  }
  try { sessionStorage.setItem("presentes:splash-seen", "1"); } catch {}
  let dismissed = false;
  let exitTimer;
  let durationTimer;
  function finish() {
    window.clearTimeout(exitTimer);
    window.clearTimeout(durationTimer);
    document.documentElement.classList.remove("splash-active");
    if (splash.open) splash.close();
    splash.remove();
    const visitor = document.getElementById("visitor-modal");
    if (visitor?.open) visitor.querySelector("[autofocus]")?.focus({preventScroll:true});
  }
  function dismiss() {
    if (dismissed) return;
    dismissed = true;
    splash.classList.add("is-leaving");
    exitTimer = window.setTimeout(finish, 340);
  }
  splash.querySelector("[data-skip-splash]").addEventListener("click", dismiss);
  splash.addEventListener("cancel", event => { event.preventDefault(); dismiss(); });
  photo.addEventListener("error", finish, {once:true});
  window.addEventListener("pageshow", event => { if (event.persisted) finish(); });
  document.documentElement.classList.add("splash-active");
  splash.showModal();
  durationTimer = window.setTimeout(dismiss, 1900);
})();
