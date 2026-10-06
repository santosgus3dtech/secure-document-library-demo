let status = "active";
let documents = [];
const role = () => document.querySelector("#role").value;
const formatSize = (bytes) => `${(bytes / 1024).toFixed(1)} KB`;

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "X-Demo-Role": role(), ...(options.headers || {}) } });
  if (!response.ok) throw new Error((await response.json()).detail || "Request failed");
  if (response.headers.get("content-type")?.includes("json")) return response.json();
  return response;
}

function render() {
  const term = document.querySelector("#search").value.toLowerCase();
  const filtered = documents.filter((item) => `${item.title} ${item.category} ${item.filename}`.toLowerCase().includes(term));
  const tbody = document.querySelector("#documents");
  tbody.innerHTML = filtered.map((item) => `<tr><td><strong>${item.title}</strong><span>${item.filename}</span></td><td>${item.category}</td><td>${formatSize(item.size_bytes)}</td><td>${item.created_at.slice(0, 10)}</td><td><span class="pill ${item.status}">${item.status}</span></td><td><div class="actions">${item.status === "active" ? `<a href="/api/documents/${item.id}/download" data-download="${item.id}">Download</a><button class="danger" data-delete="${item.id}">Delete</button>` : `<button data-restore="${item.id}">Restore</button>`}</div></td></tr>`).join("");
  document.querySelector("#empty").hidden = filtered.length > 0;
  document.querySelector("#active-count").textContent = status === "active" ? documents.length : "-";
  document.querySelector("#category-count").textContent = new Set(documents.map((item) => item.category)).size;
  document.querySelector("#storage-size").textContent = formatSize(documents.reduce((sum, item) => sum + item.size_bytes, 0));
  document.querySelectorAll("[data-delete]").forEach((button) => button.addEventListener("click", () => mutate(`/api/documents/${button.dataset.delete}`, "DELETE")));
  document.querySelectorAll("[data-restore]").forEach((button) => button.addEventListener("click", () => mutate(`/api/documents/${button.dataset.restore}/restore`, "POST")));
  document.querySelectorAll("[data-download]").forEach((link) => link.addEventListener("click", (event) => { event.preventDefault(); fetch(link.href, { headers: { "X-Demo-Role": role() } }).then((response) => response.blob()).then((blob) => { const url=URL.createObjectURL(blob); const anchor=document.createElement("a"); anchor.href=url; anchor.download=link.closest("tr").querySelector("td span").textContent; anchor.click(); URL.revokeObjectURL(url); }); }));
}

async function load() { documents = await api(`/api/documents?status=${status}`); render(); }
async function mutate(path, method) { try { await api(path, { method }); await load(); } catch (error) { window.alert(error.message); } }
document.querySelectorAll("[data-status]").forEach((button) => button.addEventListener("click", () => { status=button.dataset.status; document.querySelectorAll("[data-status]").forEach((item)=>item.classList.toggle("active", item===button)); load(); }));
document.querySelector("#search").addEventListener("input", render);
document.querySelector("#refresh").addEventListener("click", load);
document.querySelector("#role").addEventListener("change", load);
load();
