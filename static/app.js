/* ================= الحالة ================= */
let TOKEN = localStorage.getItem("token") || null;
let USER = JSON.parse(localStorage.getItem("user") || "null");
let PRODUCTS = [];
let CART = {}; // {product_id: {product, qty}}
let CITIES = [];

function can(key){
  if(!USER) return false;
  if(USER.role==="owner") return true;
  return (USER.permissions||[]).includes(key);
}
function isAdminRole(){ return USER && (USER.role==="admin"||USER.role==="owner"); }
async function loadCities(){ if(!CITIES.length){ try{ CITIES=(await api("/api/cities")).cities; }catch(e){} } return CITIES; }
// سعر سطر المنتج حسب عروض الكمية
function linePrice(p, qty){
  const o=(p.offers||[]).find(x=>Number(x.qty)===Number(qty));
  return o ? Number(o.price) : Number(p.sell_price)*qty;
}

/* ================= أدوات ================= */
const $ = (s) => document.querySelector(s);
const app = $("#app");

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2600);
}

async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (TOKEN) headers["Authorization"] = "Bearer " + TOKEN;
  const res = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "حدث خطأ");
  return data;
}

function kd(n) { return Number(n).toFixed(3); }
// تهريب أي بيانات من المستخدمين قبل عرضها (حماية من XSS)
function esc(s){ return String(s==null?"":s).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
// زر إظهار/إخفاء كلمة المرور
function togglePw(id, el){
  const inp=document.getElementById(id); if(!inp) return;
  if(inp.type==="password"){ inp.type="text"; el.textContent="🙈"; }
  else { inp.type="password"; el.textContent="👁️"; }
}
function pwField(id, label, ph){
  return `<div class="field"><label>${label}</label>
    <div style="position:relative">
      <input id="${id}" type="password" ${ph?`placeholder="${ph}"`:""} required style="padding-left:42px">
      <span onclick="togglePw('${id}',this)" style="position:absolute;left:12px;top:50%;transform:translateY(-50%);cursor:pointer;user-select:none;font-size:18px">👁️</span>
    </div></div>`;
}

function syncNav() {
  if (USER) {
    $("#guestBtns").classList.add("hidden");
    $("#userBtns").classList.remove("hidden");
    $("#dashLink").textContent = isAdminRole() ? "لوحة الأدمن" : "لوحتي";
  } else {
    $("#guestBtns").classList.remove("hidden");
    $("#userBtns").classList.add("hidden");
  }
  updateCartCount();
}

/* ================= المصادقة ================= */
function openAuth(mode) { $("#authModal").classList.add("show"); switchAuth(mode); }
function closeAuth() { $("#authModal").classList.remove("show"); $("#authAlert").innerHTML = ""; }
function switchAuth(mode) {
  const login = mode === "login";
  $("#tabLogin").classList.toggle("active", login);
  $("#tabReg").classList.toggle("active", !login);
  $("#loginForm").classList.toggle("hidden", !login);
  $("#regForm").classList.toggle("hidden", login);
  $("#authAlert").innerHTML = "";
}
function authErr(msg) { $("#authAlert").innerHTML = `<div class="alert err">${msg}</div>`; }

async function doLogin(e) {
  e.preventDefault();
  try {
    const d = await api("/api/login", { method: "POST", body: { email: $("#loginEmail").value, password: $("#loginPass").value } });
    saveSession(d);
  } catch (err) { authErr(err.message); }
  return false;
}
async function doRegister(e) {
  e.preventDefault();
  try {
    const d = await api("/api/register", { method: "POST", body: {
      name: $("#regName").value, email: $("#regEmail").value,
      phone: $("#regPhone").value, password: $("#regPass").value } });
    // الحساب قيد المراجعة — مفيش دخول تلقائي
    switchAuth("login");
    $("#authAlert").innerHTML = `<div class="alert ok">${d.message||"تم التسجيل، حسابك قيد المراجعة من الإدارة."}</div>`;
  } catch (err) { authErr(err.message); }
  return false;
}
async function saveSession(d) {
  TOKEN = d.token; USER = d.user;
  localStorage.setItem("token", TOKEN);
  // نجيب الملف الكامل (الدور + الصلاحيات)
  try { const me = await api("/api/me"); USER = {...USER, ...me}; } catch(e){}
  localStorage.setItem("user", JSON.stringify(USER));
  closeAuth(); syncNav();
  toast("أهلاً " + USER.name + " 👋");
  go(isAdminRole() ? "dashboard" : "products");
}
async function logout() {
  try { await api("/api/logout", { method: "POST" }); } catch (e) {}
  TOKEN = null; USER = null; CART = {};
  localStorage.removeItem("token"); localStorage.removeItem("user");
  syncNav(); go("home");
}

/* ================= السلة ================= */
function updateCartCount() {
  const n = Object.values(CART).reduce((s, i) => s + i.qty, 0);
  const el = $("#cartCount"); if (el) el.textContent = n;
}
function addToCart(pid) {
  if (!USER) { openAuth("login"); return; }
  const p = PRODUCTS.find((x) => x.id === pid);
  if (!CART[pid]) CART[pid] = { product: p, qty: 1 };
  else CART[pid].qty++;
  updateCartCount();
  toast("تمت الإضافة للسلة 🛒");
}

/* ================= التوجيه ================= */
async function go(route) {
  window.scrollTo(0, 0);
  if (route === "home") return renderHome();
  if (route === "products") return renderProducts();
  if (route === "dashboard") {
    if (!USER) return openAuth("login");
    return isAdminRole() ? renderAdmin() : renderDashboard();
  }
}

/* ================= الصفحة الرئيسية ================= */
function renderHome() {
  app.innerHTML = `
  <section class="hero">
    <div class="hero-in" style="grid-template-columns:1fr;max-width:820px;text-align:center">
      <div>
        <img src="/logo.png" alt="Kuwait Market" style="height:90px;background:#fff;border-radius:16px;padding:6px;margin-bottom:18px">
        <h1>منصة <em>Kuwait Market</em> لإدارة التجارة الإلكترونية</h1>
        <p>منصة متكاملة لإدارة المنتجات والطلبات وفرق العمل — مديرين ومسوّقين ومودريتور — مع متابعة لحظية للمبيعات والأرباح ونسب التسليم.</p>
        <div class="hero-actions" style="justify-content:center">
          <a class="btn" onclick="USER?go(isAdminRole()?'dashboard':'products'):openAuth('login')">${USER?'افتح لوحتي':'تسجيل الدخول'}</a>
          <a class="btn ghost" onclick="USER?go('products'):openAuth('login')">تصفّح المنتجات</a>
        </div>
        <div class="stats-row" style="justify-content:center">
          <div class="stat"><b>👥</b><small>فرق ومجموعات</small></div>
          <div class="stat"><b>📊</b><small>تقارير وأرباح</small></div>
          <div class="stat"><b>🔗</b><small>ربط إعلاني</small></div>
        </div>
      </div>
    </div>
  </section>

  <section class="about"><div class="about-in">
    <h2 class="section-title">عن المنصة</h2>
    <p>Kuwait Market منصة متكاملة لإدارة عمليات التجارة الإلكترونية للشركة: من إضافة المنتجات وتوزيع الفرق على المديرين، لتسجيل الطلبات ومتابعة التسليم والتحصيل، وصولًا لتقارير الأرباح وصرف الإعلانات لكل منتج — كله في مكان واحد وبصلاحيات دقيقة لكل دور.</p>
  </div></section>

  <section id="features"><div class="wrap">
    <h2 class="section-title">مميزات المنصة</h2>
    <p class="section-sub">كل اللي تحتاجه الشركة لإدارة الفرق والمبيعات</p>
    <div class="features">
      ${feature("👥","فرق تحت مديرين","كل مجموعة ومسوّقينها تحت مدير، وكل قائد يشوف أرقام فريقه")}
      ${feature("📊","تقارير وأرباح","نسب التأكيد والتسليم والمرتجع، وأرباح كل منتج بعد الإعلانات")}
      ${feature("🔗","ربط إعلاني بالأكواد","كود لكل منتج لمتابعة صرف ميتا وتيك توك وربح كل منتج")}
      ${feature("📦","إدارة المنتجات والطلبات","إضافة وتعديل وبحث وفلترة وتحديث جماعي للحالات")}
      ${feature("🖨️","بوليصة شحن وتحصيل","طباعة بوليصة لكل طلب بالمبلغ المطلوب تحصيله")}
      ${feature("🔒","صلاحيات دقيقة","كل مدير ومودريتور يشوف ويعمل حسب صلاحياته فقط")}
    </div>
  </div></section>

  <section id="how" style="background:#fff"><div class="wrap">
    <h2 class="section-title">إزاي بتشتغل المنصة</h2>
    <p class="section-sub">دورة العمل من الإدارة للتسليم</p>
    <div class="steps">
      ${step(1,"الإدارة تجهّز","إضافة المنتجات وأكوادها وتوزيع الفرق على المديرين")}
      ${step(2,"المسوّق يسجّل","يسجّل طلبات العملاء ويختار المنطقة والتوصيل تلقائي")}
      ${step(3,"المتابعة والتأكيد","المودريتور والمدير يتابعوا ويأكّدوا ويحدّثوا الحالات")}
      ${step(4,"التقارير والأرباح","الإدارة تشوف نسب التسليم وصرف كل منتج وصافي ربحه")}
    </div>
  </div></section>`;
  renderFooter();
}
const feature = (ic, t, d) => `<div class="feature"><div class="ic">${ic}</div><h3>${t}</h3><p>${d}</p></div>`;
const step = (n, t, d) => `<div class="step"><div class="num">${n}</div><h3 style="color:var(--blue)">${t}</h3><p class="muted">${d}</p></div>`;

/* ================= المنتجات ================= */
let CURRENT_CAT = "الكل";
async function renderProducts() {
  if (!USER) { openAuth("login"); renderHome(); return; }
  app.innerHTML = `<section><div class="wrap">
    <h2 class="section-title">المنتجات</h2>
    <p class="section-sub">اختر منتجاتك وابدأ التسويق</p>
    <div id="catBar" style="display:flex;gap:10px;flex-wrap:wrap;justify-content:center;margin-bottom:24px"></div>
    <div class="grid" id="prodGrid"><div class="empty">جاري التحميل...</div></div>
  </div></section>`;
  try {
    const d = await api("/api/products");
    PRODUCTS = d.products;
    renderCatBar();
    renderProdGrid();
  } catch (e) { $("#prodGrid").innerHTML = `<div class="empty">${e.message}</div>`; }
  renderFooter();
}
const CATEGORIES = [
  "مستلزمات السيارات",
  "الرياضة واللياقة",
  "إلكترونيات وإكسسوارات",
  "الصحة والعناية الشخصية",
  "الأزياء والإكسسوارات",
  "الأطفال والألعاب",
  "المنزل والمطبخ",
];
function renderCatBar(){
  const cats = ["الكل", ...CATEGORIES];
  if(!$("#catBar")) return;
  $("#catBar").innerHTML = cats.map(c=>
    `<button class="btn ${c===CURRENT_CAT?'':'gray'} sm" onclick="filterCat('${c.replace(/'/g,"\\'")}')">${c}</button>`).join("");
}
function filterCat(c){ CURRENT_CAT=c; renderCatBar(); renderProdGrid(); }
function renderProdGrid(){
  const list = CURRENT_CAT==="الكل" ? PRODUCTS : PRODUCTS.filter(p=>p.category===CURRENT_CAT);
  $("#prodGrid").innerHTML = list.map(productCard).join("") || `<div class="empty">لا توجد منتجات في هذا القسم</div>`;
}
function isImg(v){ return v && (v.indexOf("/uploads/")===0 || v.indexOf("http")===0); }
function thumbInner(p){ return isImg(p.image) ? `<img src="${p.image}" alt="${p.name}" style="max-width:100%;max-height:150px;object-fit:contain">` : (p.image||"📦"); }
function productCard(p) {
  const offers = (p.offers||[]).map(o=>`<span class="comm" style="background:#fff3ec;color:var(--orange)">${o.qty} بـ ${kd(o.price)}</span>`).join(" ");
  return `<div class="product" style="cursor:pointer" onclick="viewProduct(${p.id})">
    <div class="thumb">${thumbInner(p)}</div>
    <div class="body">
      <span class="cat">${esc(p.category)}</span>
      <h4>${esc(p.name)}</h4>
      <div class="price-box">
        <span class="price">${kd(p.sell_price)} د.ك</span>
      </div>
      ${offers?`<div style="display:flex;gap:6px;flex-wrap:wrap">${offers}</div>`:""}
      <button class="btn" onclick="event.stopPropagation();addToCart(${p.id})">أضف إلى السلة</button>
    </div>
  </div>`;
}

// ===== صفحة تفاصيل المنتج =====
let PM_QTY = 1;
let PM_PID = null;
async function viewProduct(pid){
  if (!USER) { openAuth("login"); return; }
  window.scrollTo(0,0);
  // اتأكد إن المنتجات محمّلة
  if(!PRODUCTS.length){ try{ PRODUCTS=(await api("/api/products")).products; }catch(e){} }
  const p = PRODUCTS.find(x=>x.id===pid); if(!p) return;
  PM_QTY = 1; PM_PID = pid;
  const imgs = (p.images&&p.images.length)?p.images.filter(isImg):(isImg(p.image)?[p.image]:[]);
  const big = imgs.length ? `<img id="pvMain" src="${imgs[0]}" style="max-width:100%;max-height:360px;object-fit:contain">` : `<div style="font-size:160px">${p.image||"📦"}</div>`;
  const thumbs = imgs.length>1 ? `<div style="display:flex;gap:8px;justify-content:center;margin-top:12px;flex-wrap:wrap">${imgs.map(u=>`<img src="${u}" onclick="document.getElementById('pvMain').src='${u}'" style="width:58px;height:58px;object-fit:cover;border-radius:8px;border:1px solid var(--line);cursor:pointer">`).join("")}</div>` : "";
  const offers = (p.offers||[]).map(o=>`<span class="comm" style="background:#fff3ec;color:var(--orange);font-size:14px;padding:6px 12px">${o.qty} قطعة بـ ${kd(o.price)} د.ك</span>`).join(" ");
  app.innerHTML = `<section><div class="wrap">
    <button class="btn gray sm" onclick="go('products')" style="margin-bottom:18px">◀ رجوع للمنتجات</button>
    <div class="dash" style="grid-template-columns:1fr 1fr;align-items:start">
      <div class="panel" style="text-align:center;background:linear-gradient(135deg,#eef9f8,#fff3ec)">${big}${thumbs}</div>
      <div class="panel">
        <span class="cat" style="color:var(--muted)">${esc(p.category)}</span>
        <h1 style="color:var(--blue);font-size:28px;margin:6px 0 10px">${esc(p.name)}</h1>
        <p class="muted" style="margin-bottom:14px">${esc(p.description)}</p>
        <div class="price" style="font-size:30px;margin-bottom:14px">${kd(p.sell_price)} د.ك</div>
        ${offers?`<div style="margin-bottom:16px"><b>🎁 عروض الكمية:</b><br><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">${offers}</div></div>`:""}
        <div class="row-between" style="margin:18px 0;padding:14px;background:#f8fafc;border-radius:12px">
          <span>الكمية</span>
          <div class="qty"><button type="button" onclick="pmQty(-1)">−</button><span id="pmQtyVal">1</span><button type="button" onclick="pmQty(1)">+</button></div>
          <span>السعر: <b id="pmLine" style="color:var(--orange)">${kd(p.sell_price)}</b> د.ك</span>
        </div>
        <div style="display:flex;gap:12px">
          <button class="btn ghost" style="flex:1;justify-content:center" onclick="addProductPage(${p.id},false)">أضف إلى السلة 🛒</button>
          <button class="btn green" style="flex:1;justify-content:center" onclick="addProductPage(${p.id},true)">إتمام الطلب ⚡</button>
        </div>
      </div>
    </div>
  </div></section>`;
  renderFooter();
}
function pmQty(d){
  PM_QTY = Math.max(1, PM_QTY + d);
  const p = PRODUCTS.find(x=>x.id===PM_PID);
  $("#pmQtyVal").textContent = PM_QTY;
  if(p) $("#pmLine").textContent = kd(linePrice(p, PM_QTY));
}
function addProductPage(pid, checkout){
  if (!USER) { openAuth("login"); return; }
  const p = PRODUCTS.find(x=>x.id===pid);
  CART[pid] = { product: p, qty: PM_QTY };
  updateCartCount();
  toast(`تمت إضافة ${PM_QTY} للسلة 🛒`);
  if(checkout) openOrder();
}

/* ================= لوحة المسوّق ================= */
let DASH_VIEW = "overview";
async function renderDashboard() {
  app.innerHTML = `<div class="dash">
    <aside class="side">
      <div class="u"><div class="av">${USER.name[0]}</div><div><b>${USER.name}</b><br><small class="muted">مسوّق</small></div></div>
      <a onclick="dashView('overview')" id="nv-overview">📊 نظرة عامة</a>
      <a onclick="dashView('orders')" id="nv-orders">📦 طلباتي</a>
      <a onclick="go('products')">🛍️ المنتجات</a>
      <a onclick="openOrder()">➕ طلب جديد</a>
      <a onclick="dashView('wallet')" id="nv-wallet">💳 محفظتي</a>
      <a onclick="dashView('password')" id="nv-password">🔑 كلمة المرور</a>
    </aside>
    <div id="dashMain"></div>
  </div>`;
  dashView("overview");
}
function dashView(v) {
  DASH_VIEW = v;
  ["overview","orders","wallet","password"].forEach(x=>{
    const el=$("#nv-"+x); if(el) el.classList.toggle("active",x===v);
  });
  if (v === "overview") dashOverview();
  if (v === "orders") dashOrders();
  if (v === "wallet") dashWallet();
  if (v === "password") $("#dashMain").innerHTML = passwordFormHTML();
}
async function dashOverview() {
  DASH_LOADER = loadMarketerDash;
  $("#dashMain").innerHTML = `<div class="panel"><div class="row-between"><h2 style="margin:0">📊 لوحتي</h2><button class="btn sm" onclick="openOrder()">➕ طلب جديد</button></div></div>`
    + dateFilterBar() + `<div id="dashBody"><div class="empty">...</div></div>`;
  loadMarketerDash();
}
async function loadMarketerDash(){
  try{
    const d = await api("/api/dashboard"+dashQuery());
    let html = statCards(d.overall);
    if(d.scope==="leader") html += breakdownTable("أعضاء المجموعة", d.by_marketer);
    $("#dashBody").innerHTML = html;
  }catch(e){ $("#dashBody").innerHTML=`<div class="empty">${e.message}</div>`; }
}
async function dashOrders() {
  const m = $("#dashMain");
  m.innerHTML = `<div class="panel"><h2>طلباتي</h2><div id="ordList">...</div></div>`;
  try {
    const d = await api("/api/my-orders");
    $("#ordList").innerHTML = d.orders.length ? ordersTable(d.orders) :
      `<div class="empty">لا توجد طلبات بعد. <a style="color:var(--orange);cursor:pointer" onclick="openOrder()">اعمل أول طلب</a></div>`;
  } catch (e) { $("#ordList").innerHTML = `<div class="empty">${e.message}</div>`; }
}
function ordersTable(orders) {
  return `<table><thead><tr><th>#</th><th>العميل</th><th>المنطقة</th><th>المنتجات</th><th>السعر</th><th>التوصيل</th><th>الإجمالي</th><th>الحالة</th></tr></thead><tbody>
    ${orders.map(o=>{const del=o.delivery||0; const grand=(o.total||0)+del; return `<tr>
      <td>#${o.id}</td>
      <td>${esc(o.customer_name)}<br><small class="muted">${esc(o.customer_phone)}</small></td>
      <td>${esc(o.area)||"—"}<br><small class="muted">${esc(o.zone)}</small></td>
      <td>${o.items.map(i=>`${esc(i.product_name)} ×${i.qty}`).join("<br>")}</td>
      <td>${kd(o.total)}</td>
      <td>${kd(del)}</td>
      <td style="font-weight:700;color:var(--orange)">${kd(grand)}</td>
      <td><span class="badge b-${o.status}">${statusAr(o.status)}</span></td>
    </tr>`;}).join("")}
  </tbody></table>`;
}
async function dashWallet() {
  const m = $("#dashMain");
  m.innerHTML = `<div class="panel">...</div>`;
  try {
    const s = await api("/api/stats");
    const w = await api("/api/my-withdrawals");
    m.innerHTML = `
    <div class="cards" style="grid-template-columns:repeat(2,1fr)">
      <div class="kpi green"><small>الرصيد المتاح للسحب</small><b>${kd(s.balance)} د.ك</b></div>
      <div class="kpi orange"><small>عمولة معلّقة (قيد التسليم)</small><b>${kd(s.pending_commission)} د.ك</b></div>
    </div>
    <div class="panel">
      <h2>طلب سحب أرباح</h2>
      <div id="wAlert"></div>
      <form onsubmit="return submitWithdraw(event)">
        <div class="field"><label>المبلغ (الرصيد المتاح ${kd(s.balance)} د.ك)</label><input id="wAmount" type="number" step="0.001" max="${s.balance}" required></div>
        <div class="field"><label>طريقة الاستلام</label>
          <select id="wMethod"><option>تحويل بنكي</option><option>محفظة إلكترونية</option><option>KNET</option></select></div>
        <div class="field"><label>التفاصيل (رقم الحساب / المحفظة)</label><input id="wDetails" required></div>
        <button class="btn green">تأكيد طلب السحب</button>
      </form>
    </div>
    <div class="panel">
      <h2>سجل طلبات السحب</h2>
      ${w.withdrawals.length ? `<table><thead><tr><th>#</th><th>المبلغ</th><th>الطريقة</th><th>الحالة</th><th>التاريخ</th></tr></thead><tbody>
        ${w.withdrawals.map(x=>`<tr><td>#${x.id}</td><td>${kd(x.amount)} د.ك</td><td>${x.method}</td>
          <td><span class="badge b-${x.status}">${statusAr(x.status)}</span></td><td class="muted">${x.created_at}</td></tr>`).join("")}
      </tbody></table>` : `<div class="empty">لا توجد طلبات سحب</div>`}
    </div>`;
  } catch (e) { m.innerHTML = `<div class="empty">${e.message}</div>`; }
}
async function submitWithdraw(e) {
  e.preventDefault();
  try {
    await api("/api/withdraw", { method:"POST", body:{
      amount: parseFloat($("#wAmount").value), method: $("#wMethod").value, details: $("#wDetails").value }});
    toast("تم إرسال طلب السحب ✅"); dashWallet();
  } catch (err) { $("#wAlert").innerHTML = `<div class="alert err">${err.message}</div>`; }
  return false;
}

/* ================= نافذة الطلب ================= */
async function openOrder() {
  if (!Object.keys(CART).length) { toast("السلة فاضية، اختر منتجات أولاً"); go("products"); return; }
  await loadCities();
  $("#cityList").innerHTML = CITIES.map(c=>`<option value="${c.city}">`).join("");
  renderCart();
  $("#orderModal").classList.add("show");
}
function closeOrder() { $("#orderModal").classList.remove("show"); }
function renderCart() {
  const items = Object.values(CART);
  $("#cartItems").innerHTML = items.map(it => {
    const p = it.product;
    const lp = linePrice(p, it.qty);
    const offerNote = (p.offers||[]).find(o=>Number(o.qty)===Number(it.qty)) ? `<span style="color:var(--orange)">عرض</span>` : "";
    return `<div class="row-between" style="padding:10px;border-bottom:1px solid var(--line)">
      <div style="flex:1"><b>${isImg(p.image)?"🖼️":p.image} ${p.name}</b><br><small class="muted">${kd(p.sell_price)} د.ك/قطعة ${offerNote}</small></div>
      <div class="qty">
        <button type="button" onclick="chQty(${p.id},-1)">−</button><span>${it.qty}</span>
        <button type="button" onclick="chQty(${p.id},1)">+</button>
      </div>
      <div style="width:90px;text-align:left;font-weight:700">${kd(lp)} د.ك</div>
      <button type="button" class="btn red sm" onclick="rmCart(${p.id})">حذف</button>
    </div>`;
  }).join("");
  recalc();
}
function chQty(pid, d) { CART[pid].qty = Math.max(1, CART[pid].qty + d); renderCart(); updateCartCount(); }
function rmCart(pid) { delete CART[pid]; updateCartCount(); if(!Object.keys(CART).length){closeOrder();go("products");return;} renderCart(); }
function currentDelivery(){
  const city = $("#custCity") ? $("#custCity").value.trim() : "";
  const c = CITIES.find(x=>x.city===city);
  return c ? c.delivery : (city? 1 : 0);
}
function onCityChange(){
  const city = $("#custCity").value.trim();
  const c = CITIES.find(x=>x.city===city);
  const info = $("#cityInfo");
  if(c){ info.innerHTML = `التقسيمة: <b>${c.zone}</b> — التوصيل: <b>${kd(c.delivery)} د.ك</b>`; }
  else if(city){ info.innerHTML = `<span style="color:var(--orange)">منطقة غير معروفة — التوصيل الافتراضي ١ د.ك</span>`; }
  else { info.innerHTML = ""; }
  recalc();
}
function recalc() {
  let sub = 0;
  Object.values(CART).forEach(it => { sub += linePrice(it.product, it.qty); });
  const del = currentDelivery();
  $("#ordSub").textContent = kd(sub);
  $("#ordDel").textContent = kd(del);
  $("#ordTotal").textContent = kd(sub + del);
}
async function submitOrder(e) {
  e.preventDefault();
  const items = Object.values(CART).map(it => ({ product_id: it.product.id, qty: it.qty }));
  try {
    const d = await api("/api/orders", { method:"POST", body:{
      items, customer:{ name:$("#custName").value, phone:$("#custPhone").value,
        city:$("#custCity").value.trim(), address:$("#custAddr").value }}});
    CART = {}; updateCartCount(); closeOrder();
    toast(`تم تسجيل الطلب #${d.order_id} ✅ الإجمالي ${kd(d.total)} د.ك`);
    go("dashboard"); setTimeout(()=>dashView("orders"),100);
  } catch (err) { $("#orderAlert").innerHTML = `<div class="alert err">${err.message}</div>`; }
  return false;
}

/* ================= لوحة الأدمن ================= */
let ADMIN_VIEW = "orders";
const ADMIN_MENU = [
  {v:"dashboard", perm:"orders", label:"📊 الإحصائيات"},
  {v:"productstats", perm:"products", label:"📦 إحصائيات المنتجات"},
  {v:"orders", perm:"orders", label:"📋 الطلبات"},
  {v:"pending", perm:"marketers", label:"🆕 طلبات التسجيل"},
  {v:"products", perm:"products", label:"🛍️ المنتجات"},
  {v:"groups", perm:"groups", label:"🗂️ المجموعات"},
  {v:"marketers", perm:"marketers", label:"👥 المسوّقين"},
  {v:"withdrawals", perm:"withdrawals", label:"💳 طلبات السحب"},
  {v:"admins", perm:"__owner__", label:"🛡️ المدراء والصلاحيات"},
  {v:"backup", perm:"__owner__", label:"💾 نسخة احتياطية"},
  {v:"password", perm:"__always__", label:"🔑 كلمة المرور"},
];
function allowedMenu(){ return ADMIN_MENU.filter(m => m.perm==="__owner__" ? USER.role==="owner" : (m.perm==="__always__" ? true : can(m.perm))); }
function renderAdmin() {
  const menu = allowedMenu();
  const roleLabel = USER.role==="owner" ? "المالك" : "مدير";
  app.innerHTML = `<div class="dash">
    <aside class="side">
      <div class="u"><div class="av" style="background:var(--blue)">${USER.name[0]}</div><div><b>${USER.name}</b><br><small class="muted">${roleLabel}</small></div></div>
      <a onclick="go('products')" style="background:var(--orange);color:#fff;font-weight:700">➕ تسجيل طلب جديد</a>
      ${menu.map(m=>`<a onclick="adminView('${m.v}')" id="av-${m.v}">${m.label}</a>`).join("")}
    </aside>
    <div id="dashMain"></div>
  </div>`;
  if(!menu.length){ $("#dashMain") && ($("#dashMain").innerHTML=`<div class="panel"><div class="empty">لا توجد صلاحيات ممنوحة لك بعد. تواصل مع المالك.</div></div>`); return; }
  const first = menu.find(m=>m.v===ADMIN_VIEW) ? ADMIN_VIEW : menu[0].v;
  adminView(first);
}
function adminView(v) {
  ADMIN_VIEW = v;
  allowedMenu().forEach(m=>{ const el=$("#av-"+m.v); if(el) el.classList.toggle("active",m.v===v); });
  if (v==="dashboard") adminDashboard();
  if (v==="productstats") adminProductStats();
  if (v==="orders") adminOrders();
  if (v==="pending") adminPending();
  if (v==="groups") adminGroups();
  if (v==="withdrawals") adminWithdrawals();
  if (v==="marketers") adminMarketers();
  if (v==="products") adminProducts();
  if (v==="admins") adminAdmins();
  if (v==="backup") adminBackup();
  if (v==="password") adminPassword();
}
function adminBackup(){
  $("#dashMain").innerHTML=`<div class="panel" style="max-width:540px"><h2>💾 نسخة احتياطية</h2>
    <p class="muted">نزّل نسخة من كل بيانات المنصة (الحسابات، المنتجات، الطلبات، المجموعات...) على جهازك. احتفظ بيها كل فترة — دي حمايتك لو حصل أي مشكلة.</p>
    <button class="btn" onclick="downloadBackup()">⬇️ تحميل نسخة احتياطية الآن</button></div>`;
}
async function downloadBackup(){
  try{
    const res=await fetch("/api/admin/backup",{headers:{"Authorization":"Bearer "+TOKEN}});
    if(!res.ok){ toast("فشل التحميل"); return; }
    const blob=await res.blob(); const url=URL.createObjectURL(blob);
    const a=document.createElement("a"); a.href=url; a.download="kuwait-market-backup-"+new Date().toISOString().slice(0,10)+".db";
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    toast("تم تحميل النسخة الاحتياطية ✅");
  }catch(e){ toast(e.message); }
}
async function adminPending(){
  const m=$("#dashMain");
  m.innerHTML=`<div class="panel"><h2>طلبات التسجيل الجديدة</h2><p class="muted">وافق أو ارفض تفعيل كل حساب جديد.</p><div id="pendList">...</div></div>`;
  try{
    const d=await api("/api/admin/pending");
    $("#pendList").innerHTML = d.pending.length ? `<table><thead><tr><th>الاسم</th><th>الإيميل</th><th>الهاتف</th><th>التاريخ</th><th>الإجراء</th></tr></thead><tbody>
      ${d.pending.map(u=>`<tr><td><b>${esc(u.name)}</b></td><td class="muted">${esc(u.email)}</td><td>${esc(u.phone)}</td><td class="muted">${u.created_at}</td>
        <td style="white-space:nowrap"><button class="btn green sm" onclick="approveUser(${u.id},'approve')">✔ موافقة</button>
        <button class="btn red sm" onclick="approveUser(${u.id},'reject')">✖ رفض</button></td></tr>`).join("")}
    </tbody></table>` : `<div class="empty">لا توجد طلبات تسجيل جديدة 👌</div>`;
  }catch(e){ $("#pendList").innerHTML=`<div class="empty">${e.message}</div>`; }
}
async function approveUser(id, action){
  try{ await api("/api/admin/approve-user",{method:"POST",body:{user_id:id,action}});
    toast(action==="approve"?"تم تفعيل الحساب ✅":"تم رفض الحساب"); adminPending();
  }catch(e){ toast(e.message); }
}
function adminPassword(){ $("#dashMain").innerHTML = passwordFormHTML(); }
function passwordFormHTML(){
  return `<div class="panel" style="max-width:460px"><h2>تغيير كلمة المرور</h2>
    <div id="pwAlert"></div>
    <form onsubmit="return changePassword(event)">
      ${pwField("pwOld","كلمة المرور الحالية")}
      ${pwField("pwNew","كلمة المرور الجديدة (6 أحرف+)")}
      ${pwField("pwNew2","تأكيد كلمة المرور الجديدة")}
      <button class="btn">حفظ كلمة المرور</button>
    </form></div>`;
}
async function changePassword(e){
  e.preventDefault();
  if($("#pwNew").value !== $("#pwNew2").value){ $("#pwAlert").innerHTML=`<div class="alert err">كلمة المرور الجديدة وتأكيدها غير متطابقين</div>`; return false; }
  try{
    await api("/api/change-password",{method:"POST",body:{old_password:$("#pwOld").value,new_password:$("#pwNew").value}});
    $("#pwAlert").innerHTML=`<div class="alert ok">تم تغيير كلمة المرور بنجاح ✅</div>`;
    $("#pwOld").value=$("#pwNew").value=$("#pwNew2").value="";
  }catch(err){ $("#pwAlert").innerHTML=`<div class="alert err">${err.message}</div>`; }
  return false;
}
// ===== لوحة الإحصائيات (مشتركة) =====
let DASH_FROM="", DASH_TO="", DASH_LOADER=null;
function dateFilterBar(){
  return `<div class="panel" style="padding:14px 18px"><div style="display:flex;gap:12px;align-items:end;flex-wrap:wrap">
    <div class="field" style="margin:0"><label>من تاريخ</label><input type="date" id="dFrom" value="${DASH_FROM}"></div>
    <div class="field" style="margin:0"><label>إلى تاريخ</label><input type="date" id="dTo" value="${DASH_TO}"></div>
    <button class="btn sm" onclick="applyDash()">تطبيق</button>
    <button class="btn gray sm" onclick="resetDash()">كل الفترات</button>
  </div></div>`;
}
function applyDash(){ DASH_FROM=$("#dFrom").value||""; DASH_TO=$("#dTo").value||""; if(DASH_LOADER)DASH_LOADER(); }
function resetDash(){ DASH_FROM=""; DASH_TO=""; if($("#dFrom"))$("#dFrom").value=""; if($("#dTo"))$("#dTo").value=""; if(DASH_LOADER)DASH_LOADER(); }
function dashQuery(){ const q=[]; if(DASH_FROM)q.push("from="+DASH_FROM); if(DASH_TO)q.push("to="+DASH_TO); return q.length?"?"+q.join("&"):""; }
function rateBar(label,pct,color){
  return `<div style="margin-bottom:12px"><div class="row-between" style="margin-bottom:4px"><span>${label}</span><b>${pct}%</b></div>
    <div style="height:10px;background:#eef2f7;border-radius:6px;overflow:hidden"><div style="height:100%;width:${Math.min(100,pct)}%;background:${color};transition:.3s"></div></div></div>`;
}
function statCards(s){
  return `<div class="cards" style="grid-template-columns:repeat(auto-fit,minmax(140px,1fr))">
    <div class="kpi"><small>إجمالي الأوردرات</small><b>${s.total}</b></div>
    <div class="kpi"><small>قيد الانتظار</small><b>${s.pending}</b></div>
    <div class="kpi orange"><small>مؤكدة</small><b>${s.confirmed_total}</b></div>
    <div class="kpi green"><small>تم التسليم</small><b>${s.delivered}</b></div>
    <div class="kpi"><small>مرتجعة</small><b style="color:#9a3412">${s.returned}</b></div>
    <div class="kpi"><small>ملغية</small><b style="color:var(--red)">${s.cancelled}</b></div>
    <div class="kpi green"><small>إجمالي المبيعات (مُسلّمة)</small><b>${kd(s.sales)} د.ك</b></div>
  </div>
  <div class="panel"><h3 style="color:var(--blue);margin-bottom:14px">النسب</h3>
    ${rateBar("نسبة التأكيد (من الإجمالي)", s.confirm_rate, "var(--orange)")}
    ${rateBar("نسبة التسليم (من المؤكد)", s.deliver_rate, "var(--green)")}
    ${rateBar("نسبة المرتجع (من المؤكد)", s.return_rate, "#9a3412")}
  </div>`;
}
function breakdownTable(title, arr){
  if(!arr||!arr.length) return "";
  return `<div class="panel"><h3 style="color:var(--blue);margin-bottom:12px">${title}</h3>
    <table><thead><tr><th>الاسم</th><th>الإجمالي</th><th>مؤكدة</th><th>مُسلّمة</th><th>مرتجعة</th><th>نسبة التسليم</th><th>المبيعات</th></tr></thead><tbody>
    ${arr.map(x=>`<tr><td><b>${esc(x.name)}</b></td><td>${x.stats.total}</td><td>${x.stats.confirmed_total}</td>
      <td style="color:var(--green)">${x.stats.delivered}</td><td style="color:#9a3412">${x.stats.returned}</td>
      <td>${x.stats.deliver_rate}%</td><td>${kd(x.stats.sales)} د.ك</td></tr>`).join("")}
    </tbody></table></div>`;
}
async function adminDashboard(){
  DASH_LOADER=loadAdminDash;
  $("#dashMain").innerHTML = `<div class="panel"><h2 style="margin:0">📊 لوحة الإحصائيات</h2></div>`+dateFilterBar()+`<div id="dashBody"><div class="empty">...</div></div>`;
  loadAdminDash();
}
function dashSectionTitle(t){ return `<h3 style="color:var(--blue);margin:22px 0 10px;border-bottom:2px solid var(--line);padding-bottom:6px">${t}</h3>`; }
async function loadAdminDash(){
  try{
    const d=await api("/api/dashboard"+dashQuery());
    let html = dashSectionTitle("📈 كل المنصة") + statCards(d.overall);
    (d.by_group||[]).forEach(g=>{ html += dashSectionTitle("🗂️ مجموعة: "+esc(g.name)) + statCards(g.stats); });
    html += dashSectionTitle("👥 حسب المسوّق") + breakdownTable("", d.by_marketer);
    $("#dashBody").innerHTML = html;
  }catch(e){ $("#dashBody").innerHTML=`<div class="empty">${e.message}</div>`; }
}
let SPEND_PID=null, SPEND_NAME="";
function openSpend(pid, name){
  SPEND_PID=pid; SPEND_NAME=name;
  const today=new Date().toISOString().slice(0,10);
  $("#spendModalBody").innerHTML=`<button class="x" onclick="closeSpend()">×</button>
    <h2>💰 صرف إعلانات: ${esc(name)}</h2>
    <div id="spendAlert"></div>
    <form onsubmit="return submitSpend(event)" style="margin-top:8px">
      <div class="row-between">
        <div class="field" style="flex:1"><label>المبلغ (د.ك)</label><input id="spAmount" type="number" step="0.001" required></div>
        <div class="field" style="flex:1"><label>التاريخ</label><input id="spDate" type="date" value="${today}" required></div>
      </div>
      <div class="field"><label>ملاحظة (اختياري)</label><input id="spNote" placeholder="مثلاً: حملة ميتا"></div>
      <button class="btn">➕ تسجيل الصرف</button>
    </form>
    <hr style="border:none;border-top:1px solid var(--line);margin:16px 0">
    <h3 style="color:var(--blue);margin-bottom:8px">سجل الصرف</h3>
    <div id="spendList">...</div>`;
  $("#spendModal").classList.add("show");
  loadSpendEntries();
}
function closeSpend(){ $("#spendModal").classList.remove("show"); if(typeof loadProductStats==="function") loadProductStats(); }
async function submitSpend(e){
  e.preventDefault();
  try{
    await api("/api/admin/add-spend",{method:"POST",body:{product_id:SPEND_PID,amount:$("#spAmount").value,date:$("#spDate").value,note:$("#spNote").value}});
    toast("تم تسجيل الصرف ✅"); $("#spAmount").value=""; $("#spNote").value=""; loadSpendEntries();
  }catch(err){ $("#spendAlert").innerHTML=`<div class="alert err">${err.message}</div>`; }
  return false;
}
async function loadSpendEntries(){
  try{
    const d=await api("/api/admin/spend-entries?product_id="+SPEND_PID);
    $("#spendList").innerHTML = d.entries.length ? `<table><thead><tr><th>التاريخ</th><th>المبلغ</th><th>ملاحظة</th><th></th></tr></thead><tbody>
      ${d.entries.map(x=>`<tr><td>${esc(x.spend_date)}</td><td><b>${kd(x.amount)} د.ك</b></td><td class="muted">${esc(x.note)}</td>
        <td><button class="btn red sm" onclick="deleteSpend(${x.id})">حذف</button></td></tr>`).join("")}
    </tbody></table>` : `<div class="empty">لا يوجد صرف مسجّل لهذا المنتج</div>`;
  }catch(e){ $("#spendList").innerHTML=`<div class="empty">${e.message}</div>`; }
}
async function deleteSpend(id){
  try{ await api("/api/admin/delete-spend",{method:"POST",body:{id}}); toast("تم الحذف"); loadSpendEntries(); }
  catch(e){ toast(e.message); }
}
async function adminProductStats(){
  DASH_LOADER=loadProductStats;
  $("#dashMain").innerHTML = `<div class="panel"><h2 style="margin:0">📦 إحصائيات المنتجات</h2></div>`+dateFilterBar()+`<div id="dashBody"><div class="empty">...</div></div>`;
  loadProductStats();
}
async function loadProductStats(){
  try{
    const d=await api("/api/admin/product-stats"+dashQuery());
    $("#dashBody").innerHTML = d.products.length ? `<div class="panel" style="overflow-x:auto"><table><thead><tr><th>المنتج</th><th>الكود</th><th>أوردرات</th><th>مُسلّمة</th><th>ملغية</th><th>نسبة التسليم</th><th>نسبة الإلغاء</th><th>إيراد المُسلّم</th><th>الجملة</th><th>صرف الإعلانات</th><th>صافي الربح</th><th></th></tr></thead><tbody>
      ${d.products.map(p=>`<tr><td><b>${esc(p.name)}</b></td><td class="muted">${esc(p.code)||'—'}</td><td>${p.total}</td>
        <td style="color:var(--green)">${p.delivered}</td><td style="color:var(--red)">${p.cancelled}</td>
        <td><b>${p.deliver_rate}%</b></td><td><b style="color:var(--red)">${p.cancel_rate}%</b></td>
        <td>${kd(p.revenue)}</td><td class="muted">${kd(p.cogs)}</td>
        <td style="color:var(--orange)">${kd(p.spend)}</td>
        <td><b style="color:${p.net_profit>=0?'var(--green)':'var(--red)'}">${kd(p.net_profit)} د.ك</b></td>
        <td><button class="btn gray sm" onclick="openSpend(${p.product_id},'${esc(p.name).replace(/'/g,"\\'")}')">💰 صرف</button></td></tr>`).join("")}
    </tbody></table>
    <p class="muted" style="margin-top:10px;font-size:13px">«صافي الربح» = إيراد المُسلّم − تكلفة الجملة − صرف الإعلانات. اضغط «💰 صرف» لتسجيل مبلغ إعلانات المنتج.</p></div>` : `<div class="empty">لا توجد بيانات منتجات بعد. سجّل صرف إعلانات من قائمة المنتجات أو هنا بعد أول طلب.</div>`;
  }catch(e){ $("#dashBody").innerHTML=`<div class="empty">${e.message}</div>`; }
}

let OF = {group:"",status:"",from:"",to:"",q:""};
let OSEL = new Set();
let ADMIN_ORDERS = [];
async function adminOrders() {
  let groups=[]; try{ groups=(await api("/api/admin/groups")).groups; }catch(e){}
  $("#dashMain").innerHTML=`<div class="panel">
    <div class="row-between" style="margin-bottom:12px"><h2 style="margin:0">الطلبات</h2>
      <button class="btn green sm" onclick="exportOrders()">⬇️ تحميل Excel</button></div>
    <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:end;margin-bottom:12px">
      <div class="field" style="margin:0;flex:1;min-width:150px"><label>بحث (اسم/هاتف)</label><input id="ofQ" value="${OF.q}" placeholder="رقم أو اسم العميل"></div>
      <div class="field" style="margin:0"><label>الحالة</label><select id="ofStatus">${['','pending','confirmed','shipped','delivered','returned','cancelled'].map(s=>`<option value="${s}" ${s===OF.status?'selected':''}>${s===''?'كل الحالات':statusAr(s)}</option>`).join('')}</select></div>
      <div class="field" style="margin:0"><label>المجموعة</label><select id="ofGroup"><option value="">الكل</option>${groups.map(g=>`<option value="${g.id}" ${String(g.id)===OF.group?'selected':''}>${esc(g.name)}</option>`).join('')}</select></div>
      <div class="field" style="margin:0"><label>من</label><input type="date" id="ofFrom" value="${OF.from}"></div>
      <div class="field" style="margin:0"><label>إلى</label><input type="date" id="ofTo" value="${OF.to}"></div>
      <button class="btn sm" onclick="applyOrderFilter()">تطبيق</button>
      <button class="btn gray sm" onclick="resetOrderFilter()">مسح</button>
    </div>
    <div id="bulkBar" style="display:none;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px;background:#fff7ed;padding:10px 14px;border-radius:10px">
      <b><span id="selCount">0</span> محدد</b> — غيّر الحالة إلى:
      <select id="bulkStatus">${ORDER_STATUSES.map(s=>`<option value="${s}">${statusAr(s)}</option>`).join('')}</select>
      <button class="btn sm" onclick="bulkUpdate()">تطبيق على المحدد</button>
    </div>
    <div id="aOrd">...</div></div>`;
  loadAdminOrders();
}
function orderFilterQuery(){ const q=[]; if(OF.q)q.push("q="+encodeURIComponent(OF.q)); if(OF.status)q.push("status="+OF.status); if(OF.group)q.push("group_id="+OF.group); if(OF.from)q.push("from="+OF.from); if(OF.to)q.push("to="+OF.to); return q.length?"?"+q.join("&"):""; }
function applyOrderFilter(){ OF={q:$("#ofQ").value,status:$("#ofStatus").value,group:$("#ofGroup").value,from:$("#ofFrom").value,to:$("#ofTo").value}; OSEL.clear(); loadAdminOrders(); }
function resetOrderFilter(){ OF={group:"",status:"",from:"",to:"",q:""}; OSEL.clear(); adminOrders(); }
async function loadAdminOrders(){
  try{
    const d=await api("/api/admin/orders"+orderFilterQuery());
    ADMIN_ORDERS=d.orders;
    $("#aOrd").innerHTML = d.orders.length ? `<table><thead><tr><th><input type="checkbox" onclick="toggleAll(this.checked)"></th><th>#</th><th>المسوّق</th><th>المجموعة</th><th>العميل</th><th>المنطقة</th><th>الإجمالي</th><th>الحالة</th><th>تغيير</th><th>🖨️</th></tr></thead><tbody>
      ${d.orders.map(o=>{const del=o.delivery||0; const grand=(o.total||0)+del; return `<tr>
        <td><input type="checkbox" ${OSEL.has(o.id)?'checked':''} onclick="toggleSel(${o.id},this.checked)"></td>
        <td>#${o.id}</td><td>${esc(o.marketer_name)}</td>
        <td>${o.group_name?`<span class="badge b-confirmed">${esc(o.group_name)}</span>`:'<span class="muted">—</span>'}</td>
        <td>${esc(o.customer_name)}<br><small class="muted">${esc(o.customer_phone)}</small></td>
        <td>${esc(o.area)||"—"}<br><small class="muted">${esc(o.zone)}</small></td>
        <td style="font-weight:700;color:var(--orange)">${kd(grand)}</td>
        <td><span class="badge b-${o.status}">${statusAr(o.status)}</span></td>
        <td><select onchange="updOrder(${o.id},this.value)">${ORDER_STATUSES.map(s=>`<option value="${s}" ${s===o.status?"selected":""}>${statusAr(s)}</option>`).join("")}</select></td>
        <td><button class="btn gray sm" onclick="printLabel(${o.id})">طباعة</button></td>
      </tr>`;}).join("")}
    </tbody></table>` : `<div class="empty">لا توجد طلبات مطابقة</div>`;
    updateBulkBar();
  }catch(e){ $("#aOrd").innerHTML=`<div class="empty">${e.message}</div>`; }
}
function toggleSel(id,ch){ if(ch)OSEL.add(id); else OSEL.delete(id); updateBulkBar(); }
function toggleAll(ch){ if(ch)ADMIN_ORDERS.forEach(o=>OSEL.add(o.id)); else OSEL.clear(); loadAdminOrders(); }
function updateBulkBar(){ const b=$("#bulkBar"); if(!b)return; b.style.display=OSEL.size?'flex':'none'; if($("#selCount"))$("#selCount").textContent=OSEL.size; }
async function bulkUpdate(){
  const status=$("#bulkStatus").value; if(!OSEL.size)return;
  try{ const r=await api("/api/admin/bulk-update-orders",{method:"POST",body:{order_ids:[...OSEL],status}}); toast("تم تحديث "+r.count+" طلب ✅"); OSEL.clear(); loadAdminOrders(); }
  catch(e){ toast(e.message); }
}
function printLabel(id){
  const o=ADMIN_ORDERS.find(x=>x.id===id); if(!o)return;
  const del=o.delivery||0;
  const items=(o.items||[]).map(i=>`${i.product_name} × ${i.qty}`).join("\n");
  $("#labelModalBody").innerHTML=`<button class="x" onclick="$('#labelModal').classList.remove('show')">×</button>
    <h2>🖨️ بوليصة شحن — طلب #${o.id}</h2>
    <p class="muted" style="font-size:13px">تقدر تعدّل أي بيان قبل الطباعة.</p>
    <div class="row-between">
      <div class="field" style="flex:1"><label>اسم العميل</label><input id="lbName" value="${escAttr(o.customer_name||'')}"></div>
      <div class="field" style="flex:1"><label>الهاتف</label><input id="lbPhone" value="${escAttr(o.customer_phone||'')}"></div>
    </div>
    <div class="row-between">
      <div class="field" style="flex:1"><label>التقسيمة</label><input id="lbZone" value="${escAttr(o.zone||'')}"></div>
      <div class="field" style="flex:1"><label>المنطقة</label><input id="lbArea" value="${escAttr(o.area||'')}"></div>
    </div>
    <div class="field"><label>العنوان</label><textarea id="lbAddr" rows="2">${escHtml(o.customer_address||'')}</textarea></div>
    <div class="field"><label>المنتجات</label><textarea id="lbItems" rows="2">${escHtml(items)}</textarea></div>
    <div class="row-between">
      <div class="field" style="flex:1"><label>قيمة المنتجات (د.ك)</label><input id="lbPrice" type="number" step="0.001" value="${kd(o.total||0)}" oninput="lbRecalc()"></div>
      <div class="field" style="flex:1"><label>سعر التوصيل (د.ك)</label><input id="lbDel" type="number" step="0.001" value="${kd(del)}" oninput="lbRecalc()"></div>
    </div>
    <div class="field"><label>طريقة عرض التوصيل على البوليصة</label>
      <select id="lbMode" onchange="lbRecalc()">
        <option value="free">توصيل مجاني (مضاف للسعر) — يُكتب: التوصيل مجاني</option>
        <option value="sep">توصيل منفصل — يُكتب سعر التوصيل</option>
      </select>
    </div>
    <div class="row-between" style="font-size:18px;font-weight:800;margin:10px 0;background:#f8fafc;padding:12px;border-radius:10px">
      <span>المطلوب تحصيله</span><span><span id="lbTotal" style="color:var(--orange)">0</span> د.ك</span>
    </div>
    <button class="btn" style="width:100%;justify-content:center" onclick="doPrintLabel(${o.id})">🖨️ طباعة البوليصة</button>`;
  $("#labelModal").classList.add("show");
  lbRecalc();
}
function lbRecalc(){
  const price=parseFloat($("#lbPrice").value)||0, del=parseFloat($("#lbDel").value)||0;
  $("#lbTotal").textContent=kd(price+del);
}
function doPrintLabel(id){
  const price=parseFloat($("#lbPrice").value)||0, del=parseFloat($("#lbDel").value)||0;
  const grand=price+del;
  const mode=$("#lbMode").value;
  const deliveryLine = mode==="free"
    ? `<div class="row"><span>التوصيل</span><b style="color:green">مجاني</b></div>`
    : `<div class="row"><span>قيمة المنتجات</span><b>${kd(price)} د.ك</b></div><div class="row"><span>التوصيل</span><b>${kd(del)} د.ك</b></div>`;
  const itemsHtml=esc($("#lbItems").value).replace(/\n/g,"<br>");
  const w=window.open("","_blank","width=420,height=640");
  if(!w){ toast("اسمح بالنوافذ المنبثقة للطباعة"); return; }
  w.document.write(`<html dir="rtl"><head><meta charset="utf-8"><title>بوليصة #${id}</title>
    <style>body{font-family:Tahoma,Arial;padding:16px;color:#111}.box{border:2px solid #111;border-radius:10px;padding:14px}h2{margin:0 0 10px;text-align:center;color:#142b52}.row{display:flex;justify-content:space-between;gap:10px;border-bottom:1px dashed #aaa;padding:6px 0}.big{font-size:22px;font-weight:bold;text-align:center;margin-top:12px;border:2px solid #111;border-radius:8px;padding:10px}</style></head>
    <body><div class="box"><h2>Kuwait Market — بوليصة شحن</h2>
    <div class="row"><span>رقم الطلب</span><b>#${id}</b></div>
    <div class="row"><span>العميل</span><b>${esc($("#lbName").value)}</b></div>
    <div class="row"><span>الهاتف</span><b>${esc($("#lbPhone").value)}</b></div>
    <div class="row"><span>التقسيمة</span><b>${esc($("#lbZone").value)}</b></div>
    <div class="row"><span>المنطقة</span><b>${esc($("#lbArea").value)}</b></div>
    <div class="row"><span>العنوان</span><b style="text-align:left">${esc($("#lbAddr").value)}</b></div>
    <div class="row"><span>المنتجات</span><b style="text-align:left">${itemsHtml}</b></div>
    ${deliveryLine}
    <div class="big">المطلوب تحصيله: ${kd(grand)} د.ك</div>
    </div><scr`+`ipt>window.onload=function(){window.print()}</scr`+`ipt></body></html>`);
  w.document.close();
}
async function exportOrders(){
  try{
    const res = await fetch("/api/admin/export-orders"+orderFilterQuery(), { headers:{ "Authorization":"Bearer "+TOKEN }});
    if(!res.ok){ toast("فشل التحميل"); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href=url; a.download="orders.csv"; document.body.appendChild(a); a.click();
    a.remove(); URL.revokeObjectURL(url);
    toast("تم تحميل الشيت ✅");
  }catch(e){ toast("فشل التحميل: "+e.message); }
}
async function adminGroups(){
  const m=$("#dashMain");
  m.innerHTML=`<div class="panel">
    <h2>إضافة مجموعة جديدة</h2>
    <div id="gAlert"></div>
    <form onsubmit="return addGroup(event)" style="display:flex;gap:10px;align-items:end">
      <div class="field" style="flex:1;margin:0"><label>اسم المجموعة / الصفة</label><input id="gName" placeholder="مثلاً: فريق القاهرة" required></div>
      <button class="btn">➕ إضافة</button>
    </form>
  </div>
  <div class="panel"><h2>المجموعات</h2><div id="gList">...</div></div>`;
  try{
    const d=await api("/api/admin/groups");
    $("#gList").innerHTML = d.groups.length ? d.groups.map(g=>`
      <div style="padding:14px;border-bottom:1px solid var(--line)">
        <div class="row-between">
          <div><b style="font-size:17px">${esc(g.name)}</b> <span class="badge b-confirmed">${g.members} عضو</span></div>
          <span class="muted" style="font-size:13px">${g.created_at}</span>
        </div>
        <div style="display:flex;align-items:center;gap:10px;margin-top:10px">
          <span class="muted" style="font-size:14px">👑 قائد المجموعة:</span>
          <select onchange="setLeader(${g.id},this.value)" style="padding:6px 10px;border:1.5px solid var(--line);border-radius:8px">
            <option value="">— بدون قائد —</option>
            ${(g.member_list||[]).map(u=>`<option value="${u.id}" ${g.leader_id===u.id?"selected":""}>${esc(u.name)}</option>`).join("")}
          </select>
          ${g.leader_name?`<span class="muted" style="font-size:13px">الحالي: <b>${esc(g.leader_name)}</b></span>`:""}
        </div>
      </div>`).join("")
      + `<p class="muted" style="margin-top:12px;padding:0 14px">القائد يشوف كل أرقام مجموعته. لإضافة أعضاء للمجموعة، روح لقسم «المسوّقين».</p>`
      : `<div class="empty">لا توجد مجموعات بعد. اعمل أول مجموعة فوق.</div>`;
  }catch(e){ $("#gList").innerHTML=`<div class="empty">${e.message}</div>`; }
}
async function addGroup(e){
  e.preventDefault();
  try{ await api("/api/admin/add-group",{method:"POST",body:{name:$("#gName").value}});
    toast("تمت إضافة المجموعة ✅"); adminGroups();
  }catch(err){ $("#gAlert").innerHTML=`<div class="alert err">${err.message}</div>`; }
  return false;
}
async function setLeader(gid, uid){
  try{ await api("/api/admin/set-leader",{method:"POST",body:{group_id:gid,user_id:uid||null}});
    toast(uid?"تم تعيين القائد ✅":"تم إزالة القائد"); adminGroups();
  }catch(e){ toast(e.message); }
}
async function updOrder(id,status){
  try { await api("/api/admin/update-order",{method:"POST",body:{order_id:id,status}});
    toast("تم تحديث الطلب"+(status==="delivered"?" وصرف العمولة ✅":"")); adminOrders();
  } catch(e){ toast(e.message); }
}
async function adminWithdrawals() {
  const m=$("#dashMain"); m.innerHTML=`<div class="panel"><h2>طلبات سحب الأرباح</h2><div id="aW">...</div></div>`;
  try {
    const d=await api("/api/admin/withdrawals");
    $("#aW").innerHTML = d.withdrawals.length ? `<table><thead><tr><th>#</th><th>المسوّق</th><th>المبلغ</th><th>الطريقة</th><th>التفاصيل</th><th>الحالة</th><th>إجراء</th></tr></thead><tbody>
      ${d.withdrawals.map(w=>`<tr><td>#${w.id}</td><td>${w.marketer_name}<br><small class="muted">${w.email}</small></td>
        <td><b>${kd(w.amount)} د.ك</b></td><td>${w.method}</td><td class="muted">${w.details||""}</td>
        <td><span class="badge b-${w.status}">${statusAr(w.status)}</span></td>
        <td>${w.status==="pending"?`<button class="btn green sm" onclick="updW(${w.id},'paid')">تم الدفع</button>
          <button class="btn red sm" onclick="updW(${w.id},'rejected')">رفض</button>`:"—"}</td></tr>`).join("")}
    </tbody></table>` : `<div class="empty">لا توجد طلبات سحب</div>`;
  } catch(e){ $("#aW").innerHTML=`<div class="empty">${e.message}</div>`; }
}
async function updW(id,status){
  try{ await api("/api/admin/update-withdrawal",{method:"POST",body:{withdrawal_id:id,status}});
    toast("تم التحديث"); adminWithdrawals(); } catch(e){ toast(e.message); }
}
async function adminMarketers() {
  const m=$("#dashMain"); m.innerHTML=`<div class="panel"><h2>المسوّقين</h2><div id="aM">...</div></div>`;
  try {
    let groups=[]; try{ groups=(await api("/api/admin/groups")).groups; }catch(e){}
    const d=await api("/api/admin/marketers");
    const grpSelect = (u)=>`<select onchange="assignGroup(${u.id},this.value)" style="padding:6px 8px;border:1.5px solid var(--line);border-radius:8px">
        <option value="">— بدون مجموعة —</option>
        ${groups.map(g=>`<option value="${g.id}" ${u.group_id===g.id?"selected":""}>${esc(g.name)}</option>`).join("")}
      </select>`;
    $("#aM").innerHTML = d.marketers.length ? `<table><thead><tr><th>#</th><th>الاسم</th><th>الإيميل</th><th>المجموعة</th><th>الرصيد</th><th>الحالة</th><th>إجراء</th></tr></thead><tbody>
      ${d.marketers.map(u=>`<tr><td>#${u.id}</td><td>${esc(u.name)}<br><small class="muted">${esc(u.phone)}</small></td><td class="muted">${esc(u.email)}</td>
        <td>${grpSelect(u)}</td>
        <td>${kd(u.balance)} د.ك</td><td><span class="badge b-${u.status}">${u.status==="active"?"نشط":"محظور"}</span></td>
        <td><button class="btn ${u.status==="active"?"red":"green"} sm" onclick="toggleBan(${u.id})">${u.status==="active"?"حظر":"فك الحظر"}</button></td></tr>`).join("")}
    </tbody></table>${groups.length?"":`<p class="muted" style="margin-top:12px">اعمل مجموعات أولاً من قسم «المجموعات» عشان تقدر تعيّن المسوّقين.</p>`}` : `<div class="empty">لا يوجد مسوّقين</div>`;
  } catch(e){ $("#aM").innerHTML=`<div class="empty">${e.message}</div>`; }
}
async function assignGroup(uid,gid){
  try{ await api("/api/admin/assign-group",{method:"POST",body:{user_id:uid,group_id:gid||null}});
    toast("تم تحديث المجموعة ✅");
  }catch(e){ toast(e.message); }
}
async function toggleBan(id){
  try{ const r=await api("/api/admin/toggle-ban",{method:"POST",body:{user_id:id}});
    toast(r.status==="banned"?"تم الحظر":"تم فك الحظر"); adminMarketers(); } catch(e){ toast(e.message); }
}
// ===== إدارة المنتجات =====
async function adminProducts(){
  const m=$("#dashMain");
  m.innerHTML=`<div class="panel">
    <div class="row-between"><h2 style="margin:0">المنتجات</h2>
      <button class="btn" onclick="adminProductForm()">➕ إضافة منتج</button></div>
    <div id="pList" style="margin-top:16px">...</div></div>`;
  try{
    const d=await api("/api/admin/products");
    const showW = d.can_see_wholesale;
    $("#pList").innerHTML = d.products.length ? `<table><thead><tr><th>الصورة</th><th>المنتج</th>${showW?'<th>سعر الجملة</th>':''}<th>سعر البيع</th><th>عروض الكمية</th><th>المخزون</th><th>الحالة</th><th>إجراءات</th></tr></thead><tbody>
      ${d.products.map(p=>{const off=(p.offers||[]).map(o=>`${o.qty}:${kd(o.price)}`).join("، ")||"—"; return `<tr>
        <td><div style="width:48px;height:48px;border-radius:8px;overflow:hidden;background:#f3f4f6;display:grid;place-items:center;font-size:24px">${isImg(p.image)?`<img src="${p.image}" style="width:100%;height:100%;object-fit:cover">`:(p.image||"📦")}</div></td>
        <td><b>${esc(p.name)}</b><br><small class="muted">${esc(p.category)}${p.code?` · كود: ${esc(p.code)}`:''}</small></td>
        ${showW?`<td style="color:var(--teal);font-weight:700">${kd(p.wholesale_price)}</td>`:''}
        <td style="font-weight:700">${kd(p.sell_price)}</td>
        <td class="muted" style="font-size:13px">${off}</td>
        <td>${p.stock}</td>
        <td><span class="badge ${p.active?'b-active':'b-cancelled'}">${p.active?'ظاهر':'مخفي'}</span></td>
        <td style="white-space:nowrap">
          <button class="btn sm gray" onclick='adminProductForm(${JSON.stringify(p).replace(/'/g,"&#39;")})'>تعديل</button>
          <button class="btn sm ${p.active?'red':'green'}" onclick="toggleProduct(${p.id})">${p.active?'إخفاء':'إظهار'}</button>
        </td></tr>`;}).join("")}
    </tbody></table>` : `<div class="empty">لا توجد منتجات. اضغط «➕ إضافة منتج».</div>`;
  }catch(e){ $("#pList").innerHTML=`<div class="empty">${e.message}</div>`; }
}

let UPLOADED_IMGS = [];
function adminProductForm(p){
  const edit = !!p;
  UPLOADED_IMGS = edit ? ((p.images&&p.images.length?p.images:(isImg(p.image)?[p.image]:[])).filter(isImg)) : [];
  $("#dashMain").innerHTML=`<div class="panel">
    <div class="row-between"><h2 style="margin:0">${edit?'تعديل منتج':'إضافة منتج جديد'}</h2>
      <button class="btn gray sm" onclick="adminProducts()">◀ رجوع للقائمة</button></div>
    <div id="apAlert" style="margin-top:12px"></div>
    <form onsubmit="return saveProduct(event, ${edit?p.id:'null'})" style="margin-top:12px">
      <div class="field"><label>صور المنتج (تقدر ترفع أكتر من صورة)</label>
        <div id="imgStrip" style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px"></div>
        <input type="file" id="apFile" accept="image/*" multiple onchange="pickImages(this)" style="font-size:14px">
        <div class="muted" style="font-size:12px;margin-top:6px">JPG / PNG — بتتصغّر تلقائيًا. أول صورة هي الرئيسية.</div>
        <div id="upMsg" class="muted" style="font-size:13px;margin-top:4px"></div>
      </div>
      <div class="row-between">
        <div class="field" style="flex:2"><label>اسم المنتج</label><input id="apName" value="${edit?escAttr(p.name):''}" required></div>
        <div class="field" style="flex:1"><label>كود المنتج (للإعلانات)</label><input id="apCode" value="${edit?escAttr(p.code||''):''}" placeholder="مثلاً: KM-105"></div>
      </div>
      <div class="field"><label>الوصف</label><textarea id="apDesc" rows="2">${edit?escHtml(p.description||''):''}</textarea></div>
      <div class="field"><label>القسم</label><select id="apCat">${
        ["<option value=''>— اختر القسم —</option>", ...CATEGORIES.map(c=>`<option value="${escAttr(c)}"${edit&&p.category===c?' selected':''}>${c}</option>`)].join("")
      }</select></div>
      <div class="row-between">
        ${can("wholesale")?`<div class="field" style="flex:1"><label>💼 سعر الجملة (للأدمن فقط)</label><input id="apWholesale" type="number" step="0.001" value="${edit&&p.wholesale_price!=null?p.wholesale_price:''}" required></div>`:''}
        <div class="field" style="flex:1"><label>🏷️ سعر البيع (يظهر للمسوّق)</label><input id="apSell" type="number" step="0.001" value="${edit?p.sell_price:''}" required></div>
        <div class="field" style="flex:1"><label>المخزون</label><input id="apStock" type="number" value="${edit?p.stock:100}" required></div>
      </div>
      <div class="field"><label>🎁 عروض الكمية (اختياري) — السعر الإجمالي للكمية</label>
        <div class="row-between" style="gap:10px">
          <div style="flex:1"><small class="muted">سعر القطعتين</small><input id="apOff2" type="number" step="0.001" value="${edit?offVal(p,2):''}" placeholder="إجمالي ٢ قطعة"></div>
          <div style="flex:1"><small class="muted">سعر الـ٣</small><input id="apOff3" type="number" step="0.001" value="${edit?offVal(p,3):''}" placeholder="إجمالي ٣ قطع"></div>
          <div style="flex:1"><small class="muted">سعر الـ٤</small><input id="apOff4" type="number" step="0.001" value="${edit?offVal(p,4):''}" placeholder="إجمالي ٤ قطع"></div>
        </div>
      </div>
      <button class="btn">${edit?'حفظ التعديلات':'إضافة المنتج'}</button>
    </form></div>`;
  renderImgStrip();
}
function offVal(p, q){ const o=(p.offers||[]).find(x=>Number(x.qty)===q); return o?o.price:''; }

function escAttr(s){ return String(s).replace(/"/g,"&quot;"); }
function escHtml(s){ return String(s).replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

function renderImgStrip(){
  const el=$("#imgStrip"); if(!el) return;
  el.innerHTML = UPLOADED_IMGS.length ? UPLOADED_IMGS.map((u,i)=>`<div style="position:relative;width:72px;height:72px;border-radius:8px;overflow:hidden;border:1px solid var(--line)">
    <img src="${u}" style="width:100%;height:100%;object-fit:cover">
    ${i===0?'<span style="position:absolute;bottom:0;right:0;background:var(--orange);color:#fff;font-size:10px;padding:1px 4px">رئيسية</span>':''}
    <button type="button" onclick="removeImg(${i})" style="position:absolute;top:0;left:0;background:var(--red);color:#fff;border:none;width:20px;height:20px;cursor:pointer;font-size:12px;line-height:1">×</button>
  </div>`).join("") : `<div class="muted" style="font-size:13px">لا توجد صور بعد — ارفع صورة أو أكثر</div>`;
}
function removeImg(i){ UPLOADED_IMGS.splice(i,1); renderImgStrip(); }

// تصغير الصور في المتصفح قبل رفعها (متعددة)
function pickImages(input){
  const files=[...input.files]; if(!files.length) return;
  $("#upMsg").textContent="جاري رفع الصور...";
  let done=0;
  files.forEach(file=>{
    const reader=new FileReader();
    reader.onload=(ev)=>{
      const img=new Image();
      img.onload=async()=>{
        const max=800; let {width,height}=img;
        if(width>max){ height=height*max/width; width=max; }
        const c=document.createElement("canvas"); c.width=width; c.height=height;
        c.getContext("2d").drawImage(img,0,0,width,height);
        const b64=c.toDataURL("image/jpeg",0.85);
        try{ const d=await api("/api/admin/upload-image",{method:"POST",body:{data:b64,ext:"jpg"}}); UPLOADED_IMGS.push(d.url); renderImgStrip(); }
        catch(e){ $("#upMsg").textContent="فشل رفع صورة: "+e.message; }
        done++; if(done===files.length) $("#upMsg").textContent="تم رفع الصور ✅";
      };
      img.src=ev.target.result;
    };
    reader.readAsDataURL(file);
  });
  input.value="";
}

async function saveProduct(e, editId){
  e.preventDefault();
  const offers=[];
  [[2,"apOff2"],[3,"apOff3"],[4,"apOff4"]].forEach(([q,id])=>{
    const el=$("#"+id); const v=el&&el.value?parseFloat(el.value):0;
    if(v>0) offers.push({qty:q, price:v});
  });
  const body={
    name:$("#apName").value, code:$("#apCode")?$("#apCode").value:"", description:$("#apDesc").value, category:$("#apCat").value,
    images: UPLOADED_IMGS, image: UPLOADED_IMGS[0] || "📦",
    sell_price:$("#apSell").value, offers, stock:$("#apStock").value };
  const wEl=$("#apWholesale"); if(wEl) body.wholesale_price=wEl.value;
  try{
    if(editId){ body.id=editId; await api("/api/admin/update-product",{method:"POST",body});
      toast("تم حفظ التعديلات ✅"); }
    else { await api("/api/admin/add-product",{method:"POST",body}); toast("تمت إضافة المنتج ✅"); }
    adminProducts();
  } catch(err){ $("#apAlert").innerHTML=`<div class="alert err">${err.message}</div>`; }
  return false;
}
async function toggleProduct(id){
  try{ await api("/api/admin/toggle-product",{method:"POST",body:{id}}); toast("تم التحديث"); adminProducts(); }
  catch(e){ toast(e.message); }
}

// ===== المدراء والصلاحيات (للمالك فقط) =====
let PERM_CATALOG = {};
async function adminAdmins(){
  const m=$("#dashMain");
  m.innerHTML=`<div class="panel"><h2>إضافة مدير جديد</h2><div id="adAlert"></div><div id="addAdminForm">...</div></div>
    <div class="panel"><h2>المدراء الحاليون</h2><div id="adList">...</div></div>`;
  try{
    const d=await api("/api/admin/admins");
    PERM_CATALOG=d.perm_catalog;
    const permChecks = (selected)=>Object.entries(PERM_CATALOG).map(([k,label])=>
      `<label style="display:inline-flex;align-items:center;gap:6px;margin:4px 12px 4px 0;font-weight:500">
        <input type="checkbox" value="${k}" ${selected.includes(k)?"checked":""}> ${label}</label>`).join("");
    $("#addAdminForm").innerHTML=`<form onsubmit="return addAdmin(event)">
      <div class="row-between">
        <div class="field" style="flex:1"><label>الاسم</label><input id="naName" required></div>
        <div class="field" style="flex:1"><label>الإيميل</label><input id="naEmail" type="email" required></div>
      </div>
      <div class="row-between">
        <div class="field" style="flex:1"><label>الهاتف</label><input id="naPhone"></div>
        <div style="flex:1">${pwField("naPass","كلمة المرور (6 أحرف+)")}</div>
      </div>
      <div class="field"><label>الصلاحيات</label><div id="naPerms" style="background:#f8fafc;border-radius:10px;padding:10px">${permChecks([])}</div></div>
      <button class="btn">➕ إضافة المدير</button>
    </form>`;
    $("#adList").innerHTML = d.admins.map(a=>{
      if(a.role==="owner") return `<div class="row-between" style="padding:12px;border-bottom:1px solid var(--line)">
        <div><b>${a.name}</b> <span class="badge b-active">المالك</span><br><small class="muted">${a.email}</small></div>
        <div class="muted">كل الصلاحيات</div></div>`;
      return `<div style="padding:12px;border-bottom:1px solid var(--line)">
        <div class="row-between"><div><b>${a.name}</b> <span class="badge ${a.status==='active'?'b-active':'b-banned'}">${a.status==='active'?'نشط':'موقوف'}</span><br><small class="muted">${a.email}</small></div>
          <div><button class="btn sm ${a.status==='active'?'red':'green'}" onclick="toggleAdminStatus(${a.id},'${a.status==='active'?'banned':'active'}')">${a.status==='active'?'إيقاف':'تفعيل'}</button></div></div>
        <div id="perms-${a.id}" style="margin-top:8px;background:#f8fafc;border-radius:10px;padding:10px">${permChecks(a.permissions)}</div>
        <button class="btn sm blue" style="margin-top:8px" onclick="saveAdminPerms(${a.id})">حفظ صلاحياته</button>
      </div>`;
    }).join("");
  }catch(e){ $("#adList").innerHTML=`<div class="empty">${e.message}</div>`; }
}
async function addAdmin(e){
  e.preventDefault();
  const perms=[...$("#naPerms").querySelectorAll("input:checked")].map(x=>x.value);
  try{
    await api("/api/admin/add-admin",{method:"POST",body:{name:$("#naName").value,email:$("#naEmail").value,phone:$("#naPhone").value,password:$("#naPass").value,permissions:perms}});
    toast("تم إضافة المدير ✅"); adminAdmins();
  }catch(err){ $("#adAlert").innerHTML=`<div class="alert err">${err.message}</div>`; }
  return false;
}
async function saveAdminPerms(id){
  const perms=[...$("#perms-"+id).querySelectorAll("input:checked")].map(x=>x.value);
  try{ await api("/api/admin/update-admin",{method:"POST",body:{user_id:id,permissions:perms}}); toast("تم حفظ الصلاحيات ✅"); }
  catch(e){ toast(e.message); }
}
async function toggleAdminStatus(id,status){
  try{ await api("/api/admin/update-admin",{method:"POST",body:{user_id:id,status}}); toast("تم التحديث"); adminAdmins(); }
  catch(e){ toast(e.message); }
}

/* ================= مشترك ================= */
function statusAr(s){return{pending:"قيد الانتظار",confirmed:"مؤكد",shipped:"قيد الشحن",delivered:"تم التسليم",
  cancelled:"ملغي",returned:"مرتجع",paid:"مدفوع",rejected:"مرفوض"}[s]||s;}
const ORDER_STATUSES=["pending","confirmed","shipped","delivered","returned","cancelled"];
function renderFooter(){
  if ($("#ftr")) return;
  const f=document.createElement("footer"); f.id="ftr";
  f.innerHTML=`<div class="logo" style="font-size:24px;font-weight:800;justify-content:center;color:#fff">
      <img src="/logo.png" alt="Kuwait Market" style="height:46px;background:#fff;border-radius:10px;padding:3px">
      <span style="color:#fff">Kuwait</span> <span style="color:var(--orange)">Market</span></div>
    <p>منصة متكاملة لإدارة التجارة الإلكترونية وفرق العمل</p>
    <p>© Kuwait Market 2026</p>`;
  document.body.appendChild(f);
}

/* ================= الإقلاع ================= */
(async function init(){
  syncNav();
  if (USER) { try { const me=await api("/api/me"); USER={...USER,...me}; localStorage.setItem("user",JSON.stringify(USER)); } catch(e){ /* توكن منتهي */ TOKEN=null;USER=null;localStorage.clear();syncNav(); } }
  go("home");
})();
