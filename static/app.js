/* ================= الحالة ================= */
let TOKEN = localStorage.getItem("token") || null;
let USER = JSON.parse(localStorage.getItem("user") || "null");
let PRODUCTS = [];
let CART = {}; // {product_id: {product, qty, sell_price}}

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

function syncNav() {
  if (USER) {
    $("#guestBtns").classList.add("hidden");
    $("#userBtns").classList.remove("hidden");
    $("#dashLink").textContent = USER.role === "admin" ? "لوحة الأدمن" : "لوحتي";
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
    saveSession(d);
  } catch (err) { authErr(err.message); }
  return false;
}
function saveSession(d) {
  TOKEN = d.token; USER = d.user;
  localStorage.setItem("token", TOKEN);
  localStorage.setItem("user", JSON.stringify(USER));
  closeAuth(); syncNav();
  toast("أهلاً " + USER.name + " 👋");
  go(USER.role === "admin" ? "dashboard" : "products");
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
  if (USER.role === "admin") { toast("الأدمن مايعملش طلبات"); return; }
  const p = PRODUCTS.find((x) => x.id === pid);
  if (!CART[pid]) CART[pid] = { product: p, qty: 1, sell_price: p.min_price };
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
    return USER.role === "admin" ? renderAdmin() : renderDashboard();
  }
}

/* ================= الصفحة الرئيسية ================= */
function renderHome() {
  app.innerHTML = `
  <section class="hero">
    <div class="hero-in">
      <div>
        <img src="/logo.png" alt="Kuwait Market" style="height:90px;background:#fff;border-radius:16px;padding:6px;margin-bottom:18px">
        <h1>ابدأ تجارتك الإلكترونية في الكويت <em>بدون رأس مال</em></h1>
        <p>أدِر متجرك، سوّق منتجاتنا، واكسب عمولة على كل بيعة. إحنا بنوفرلك المنتج والتغليف والشحن والتحصيل.</p>
        <div class="hero-actions">
          <a class="btn" onclick="USER?go('products'):openAuth('register')">ابدأ الآن مجاناً</a>
          <a class="btn ghost" onclick="go('products')">تصفّح المنتجات</a>
        </div>
        <div class="stats-row">
          <div class="stat"><b>+5K</b><small>تاجر نشط</small></div>
          <div class="stat"><b>15K+</b><small>منتج</small></div>
          <div class="stat"><b>100%</b><small>مجاني</small></div>
        </div>
      </div>
      <div class="hero-card">
        <div style="font-weight:800;margin-bottom:14px">📊 مبيعات اليوم</div>
        <div class="mini"><span>الطلبات</span><b>234</b></div>
        <div class="mini"><span>الزيارات</span><b>1.2K</b></div>
        <div class="mini"><span>رضا العملاء</span><b>98%</b></div>
      </div>
    </div>
  </section>

  <section class="about"><div class="about-in">
    <h2 class="section-title">من نحن؟</h2>
    <p>Kuwait Market أول منصة في الكويت بتقدّم خدمات متكاملة لكل من يحلم ببناء كيان تجاري إلكتروني، بأعلى معدلات ربح ومن غير أي تكاليف. بنوفرلك الدورة الكاملة لعملية البيع: المنتجات الأكثر مبيعاً، التجهيز والتغليف، والشحن من خلال مناديبنا وفروعنا في كل أنحاء الكويت.</p>
  </div></section>

  <section id="features"><div class="wrap">
    <h2 class="section-title">ليه تنضم لـ Kuwait Market؟</h2>
    <p class="section-sub">كل اللي محتاجه عشان تبدأ تجارتك وتكسب</p>
    <div class="features">
      ${feature("💰","رأس مال بسيط","مشروع أحلامك برأس مال بسيط للإعلانات فقط")}
      ${feature("🏷️","مرونة في التسعير","حدّد سعر البيع بين حد أدنى وأعلى يناسبك")}
      ${feature("📣","مهمتك التسويق فقط","إحنا بنتكفل بالباقي، إنت بس سوّق")}
      ${feature("📦","تنوع المنتجات","أكثر من 15000 منتج متجدد باستمرار")}
      ${feature("📈","عمولة وربح صافي","أكبر العمولات والأرباح اللي تحلم بيها")}
      ${feature("💳","سحب أرباحك بسهولة","أكثر من طريقة دفع لسحب أرباحك فوراً")}
    </div>
  </div></section>

  <section id="how" style="background:#fff"><div class="wrap">
    <h2 class="section-title">كيف أبدأ؟</h2>
    <p class="section-sub">4 خطوات بسيطة وتبدأ تكسب</p>
    <div class="steps">
      ${step(1,"أنشئ حساب","سجّل حساب جديد مجاناً في دقيقة")}
      ${step(2,"اختر العروض","تصفّح المنتجات واختار اللي يناسبك")}
      ${step(3,"سوّق المنتجات","انشر على السوشيال ميديا وهات عملاء")}
      ${step(4,"اكسب العمولة","كل بيعة توصل، عمولتك تدخل رصيدك")}
    </div>
  </div></section>`;
  renderFooter();
}
const feature = (ic, t, d) => `<div class="feature"><div class="ic">${ic}</div><h3>${t}</h3><p>${d}</p></div>`;
const step = (n, t, d) => `<div class="step"><div class="num">${n}</div><h3 style="color:var(--blue)">${t}</h3><p class="muted">${d}</p></div>`;

/* ================= المنتجات ================= */
async function renderProducts() {
  app.innerHTML = `<section><div class="wrap">
    <h2 class="section-title">المنتجات</h2>
    <p class="section-sub">اختر منتجاتك وابدأ التسويق</p>
    <div class="grid" id="prodGrid"><div class="empty">جاري التحميل...</div></div>
  </div></section>`;
  try {
    const d = await api("/api/products");
    PRODUCTS = d.products;
    $("#prodGrid").innerHTML = PRODUCTS.map(productCard).join("") ||
      `<div class="empty">لا توجد منتجات بعد</div>`;
  } catch (e) { $("#prodGrid").innerHTML = `<div class="empty">${e.message}</div>`; }
  renderFooter();
}
function productCard(p) {
  return `<div class="product">
    <div class="thumb">${p.image || "📦"}</div>
    <div class="body">
      <span class="cat">${p.category || ""}</span>
      <h4>${p.name}</h4>
      <div class="price-box">
        <span class="price">${kd(p.min_price)} د.ك</span>
        <span class="comm">عمولة ${kd(p.commission)}</span>
      </div>
      <div class="muted" style="font-size:12px">البيع بين ${kd(p.min_price)} و ${kd(p.max_price)} د.ك</div>
      <button class="btn" onclick="addToCart(${p.id})">أضف إلى السلة</button>
    </div>
  </div>`;
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
    </aside>
    <div id="dashMain"></div>
  </div>`;
  dashView("overview");
}
function dashView(v) {
  DASH_VIEW = v;
  ["overview","orders","wallet"].forEach(x=>{
    const el=$("#nv-"+x); if(el) el.classList.toggle("active",x===v);
  });
  if (v === "overview") dashOverview();
  if (v === "orders") dashOrders();
  if (v === "wallet") dashWallet();
}
async function dashOverview() {
  const m = $("#dashMain");
  m.innerHTML = `<div class="cards"><div class="empty">...</div></div>`;
  try {
    const s = await api("/api/stats");
    m.innerHTML = `
    <div class="cards">
      <div class="kpi"><small>إجمالي الطلبات</small><b>${s.total_orders}</b></div>
      <div class="kpi green"><small>طلبات تم تسليمها</small><b>${s.delivered}</b></div>
      <div class="kpi orange"><small>عمولة معلّقة</small><b>${kd(s.pending_commission)}</b></div>
      <div class="kpi green"><small>الرصيد القابل للسحب</small><b>${kd(s.balance)} د.ك</b></div>
    </div>
    <div class="panel">
      <div class="row-between"><h2>ابدأ بيعة جديدة</h2><button class="btn" onclick="openOrder()">➕ طلب جديد</button></div>
      <p class="muted">إجمالي ما كسبته منذ البداية: <b style="color:var(--green)">${kd(s.total_earned)} د.ك</b></p>
    </div>`;
  } catch (e) { m.innerHTML = `<div class="empty">${e.message}</div>`; }
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
  return `<table><thead><tr><th>#</th><th>العميل</th><th>المنتجات</th><th>الإجمالي</th><th>عمولتك</th><th>الحالة</th><th>التاريخ</th></tr></thead><tbody>
    ${orders.map(o=>`<tr>
      <td>#${o.id}</td>
      <td>${o.customer_name}<br><small class="muted">${o.customer_phone}</small></td>
      <td>${o.items.map(i=>`${i.product_name} ×${i.qty}`).join("<br>")}</td>
      <td>${kd(o.total)} د.ك</td>
      <td style="color:var(--green);font-weight:700">${kd(o.commission)}</td>
      <td><span class="badge b-${o.status}">${statusAr(o.status)}</span></td>
      <td class="muted">${o.created_at}</td>
    </tr>`).join("")}
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
function openOrder() {
  if (!Object.keys(CART).length) { toast("السلة فاضية، اختر منتجات أولاً"); go("products"); return; }
  renderCart();
  $("#orderModal").classList.add("show");
}
function closeOrder() { $("#orderModal").classList.remove("show"); }
function renderCart() {
  const items = Object.values(CART);
  $("#cartItems").innerHTML = items.map(it => {
    const p = it.product;
    return `<div class="row-between" style="padding:10px;border-bottom:1px solid var(--line)">
      <div><b>${p.image} ${p.name}</b><br><small class="muted">البيع بين ${kd(p.min_price)} و ${kd(p.max_price)} د.ك</small></div>
      <div class="qty">
        <button type="button" onclick="chQty(${p.id},-1)">−</button><span>${it.qty}</span>
        <button type="button" onclick="chQty(${p.id},1)">+</button>
      </div>
      <div class="field" style="margin:0;width:120px">
        <label style="font-size:12px">سعر البيع</label>
        <input type="number" step="0.001" min="${p.min_price}" max="${p.max_price}" value="${it.sell_price}" onchange="chPrice(${p.id},this.value)">
      </div>
      <button type="button" class="btn red sm" onclick="rmCart(${p.id})">حذف</button>
    </div>`;
  }).join("");
  recalc();
}
function chQty(pid, d) { CART[pid].qty = Math.max(1, CART[pid].qty + d); renderCart(); updateCartCount(); }
function chPrice(pid, v) { CART[pid].sell_price = parseFloat(v) || CART[pid].product.min_price; recalc(); }
function rmCart(pid) { delete CART[pid]; updateCartCount(); if(!Object.keys(CART).length){closeOrder();go("products");return;} renderCart(); }
function recalc() {
  let total = 0, comm = 0;
  Object.values(CART).forEach(it => { total += it.sell_price * it.qty; comm += it.product.commission * it.qty; });
  $("#ordTotal").textContent = kd(total);
  $("#ordComm").textContent = kd(comm);
}
async function submitOrder(e) {
  e.preventDefault();
  const items = Object.values(CART).map(it => ({ product_id: it.product.id, qty: it.qty, sell_price: it.sell_price }));
  try {
    const d = await api("/api/orders", { method:"POST", body:{
      items, customer:{ name:$("#custName").value, phone:$("#custPhone").value,
        address:$("#custAddr").value, governorate:$("#custGov").value }}});
    CART = {}; updateCartCount(); closeOrder();
    toast(`تم تسجيل الطلب #${d.order_id} ✅ عمولتك ${kd(d.commission)} د.ك`);
    go("dashboard"); setTimeout(()=>dashView("orders"),100);
  } catch (err) { $("#orderAlert").innerHTML = `<div class="alert err">${err.message}</div>`; }
  return false;
}

/* ================= لوحة الأدمن ================= */
let ADMIN_VIEW = "orders";
function renderAdmin() {
  app.innerHTML = `<div class="dash">
    <aside class="side">
      <div class="u"><div class="av" style="background:var(--blue)">${USER.name[0]}</div><div><b>${USER.name}</b><br><small class="muted">أدمن</small></div></div>
      <a onclick="adminView('orders')" id="av-orders">📦 الطلبات</a>
      <a onclick="adminView('withdrawals')" id="av-withdrawals">💳 طلبات السحب</a>
      <a onclick="adminView('marketers')" id="av-marketers">👥 المسوّقين</a>
      <a onclick="adminView('addprod')" id="av-addprod">➕ إضافة منتج</a>
    </aside>
    <div id="dashMain"></div>
  </div>`;
  adminView("orders");
}
function adminView(v) {
  ADMIN_VIEW = v;
  ["orders","withdrawals","marketers","addprod"].forEach(x=>{
    const el=$("#av-"+x); if(el) el.classList.toggle("active",x===v);
  });
  if (v==="orders") adminOrders();
  if (v==="withdrawals") adminWithdrawals();
  if (v==="marketers") adminMarketers();
  if (v==="addprod") adminAddProduct();
}
async function adminOrders() {
  const m=$("#dashMain"); m.innerHTML=`<div class="panel"><h2>كل الطلبات</h2><div id="aOrd">...</div></div>`;
  try {
    const d=await api("/api/admin/orders");
    $("#aOrd").innerHTML = d.orders.length ? `<table><thead><tr><th>#</th><th>المسوّق</th><th>العميل</th><th>الإجمالي</th><th>العمولة</th><th>الحالة</th><th>تغيير</th></tr></thead><tbody>
      ${d.orders.map(o=>`<tr><td>#${o.id}</td><td>${o.marketer_name}</td>
        <td>${o.customer_name}<br><small class="muted">${o.customer_phone} — ${o.governorate||""}</small></td>
        <td>${kd(o.total)}</td><td style="color:var(--green)">${kd(o.commission)}</td>
        <td><span class="badge b-${o.status}">${statusAr(o.status)}</span></td>
        <td><select onchange="updOrder(${o.id},this.value)">
          ${["pending","confirmed","shipped","delivered","cancelled"].map(s=>`<option value="${s}" ${s===o.status?"selected":""}>${statusAr(s)}</option>`).join("")}
        </select></td></tr>`).join("")}
    </tbody></table>` : `<div class="empty">لا توجد طلبات</div>`;
  } catch(e){ $("#aOrd").innerHTML=`<div class="empty">${e.message}</div>`; }
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
    const d=await api("/api/admin/marketers");
    $("#aM").innerHTML = d.marketers.length ? `<table><thead><tr><th>#</th><th>الاسم</th><th>الإيميل</th><th>الهاتف</th><th>الرصيد</th><th>الحالة</th><th>إجراء</th></tr></thead><tbody>
      ${d.marketers.map(u=>`<tr><td>#${u.id}</td><td>${u.name}</td><td class="muted">${u.email}</td><td>${u.phone||""}</td>
        <td>${kd(u.balance)} د.ك</td><td><span class="badge b-${u.status}">${u.status==="active"?"نشط":"محظور"}</span></td>
        <td><button class="btn ${u.status==="active"?"red":"green"} sm" onclick="toggleBan(${u.id})">${u.status==="active"?"حظر":"فك الحظر"}</button></td></tr>`).join("")}
    </tbody></table>` : `<div class="empty">لا يوجد مسوّقين</div>`;
  } catch(e){ $("#aM").innerHTML=`<div class="empty">${e.message}</div>`; }
}
async function toggleBan(id){
  try{ const r=await api("/api/admin/toggle-ban",{method:"POST",body:{user_id:id}});
    toast(r.status==="banned"?"تم الحظر":"تم فك الحظر"); adminMarketers(); } catch(e){ toast(e.message); }
}
function adminAddProduct() {
  $("#dashMain").innerHTML = `<div class="panel"><h2>إضافة منتج جديد</h2>
    <div id="apAlert"></div>
    <form onsubmit="return addProduct(event)">
      <div class="field"><label>اسم المنتج</label><input id="apName" required></div>
      <div class="field"><label>الوصف</label><textarea id="apDesc" rows="2"></textarea></div>
      <div class="row-between">
        <div class="field" style="flex:1"><label>التصنيف</label><input id="apCat"></div>
        <div class="field" style="width:100px"><label>أيقونة</label><input id="apImg" value="📦"></div>
      </div>
      <div class="row-between">
        <div class="field" style="flex:1"><label>سعر التكلفة</label><input id="apBase" type="number" step="0.001" required></div>
        <div class="field" style="flex:1"><label>أقل سعر بيع</label><input id="apMin" type="number" step="0.001" required></div>
        <div class="field" style="flex:1"><label>أعلى سعر بيع</label><input id="apMax" type="number" step="0.001" required></div>
      </div>
      <div class="row-between">
        <div class="field" style="flex:1"><label>العمولة</label><input id="apComm" type="number" step="0.001" required></div>
        <div class="field" style="flex:1"><label>المخزون</label><input id="apStock" type="number" value="100" required></div>
      </div>
      <button class="btn">إضافة المنتج</button>
    </form></div>`;
}
async function addProduct(e){
  e.preventDefault();
  try{
    await api("/api/admin/add-product",{method:"POST",body:{
      name:$("#apName").value, description:$("#apDesc").value, category:$("#apCat").value, image:$("#apImg").value,
      base_price:$("#apBase").value, min_price:$("#apMin").value, max_price:$("#apMax").value,
      commission:$("#apComm").value, stock:$("#apStock").value }});
    toast("تمت إضافة المنتج ✅"); adminAddProduct();
  } catch(err){ $("#apAlert").innerHTML=`<div class="alert err">${err.message}</div>`; }
  return false;
}

/* ================= مشترك ================= */
function statusAr(s){return{pending:"قيد الانتظار",confirmed:"مؤكد",shipped:"قيد الشحن",delivered:"تم التسليم",
  cancelled:"ملغي",paid:"مدفوع",rejected:"مرفوض"}[s]||s;}
function renderFooter(){
  if ($("#ftr")) return;
  const f=document.createElement("footer"); f.id="ftr";
  f.innerHTML=`<div class="logo" style="font-size:24px;font-weight:800;justify-content:center;color:#fff">
      <img src="/logo.png" alt="Kuwait Market" style="height:46px;background:#fff;border-radius:10px;padding:3px">
      <span style="color:#fff">Kuwait</span> <span style="color:var(--orange)">Market</span></div>
    <p>منصة رائدة في التجارة الإلكترونية في الكويت — سوّق واربح بسهولة</p>
    <p>© Kuwait Market 2026</p>`;
  document.body.appendChild(f);
}

/* ================= الإقلاع ================= */
(async function init(){
  syncNav();
  if (USER) { try { const me=await api("/api/me"); USER={...USER,...me}; localStorage.setItem("user",JSON.stringify(USER)); } catch(e){ /* توكن منتهي */ TOKEN=null;USER=null;localStorage.clear();syncNav(); } }
  go("home");
})();
