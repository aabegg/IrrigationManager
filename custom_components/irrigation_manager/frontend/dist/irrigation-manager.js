const O = globalThis, Q = O.ShadowRoot && (O.ShadyCSS === void 0 || O.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype, Y = /* @__PURE__ */ Symbol(), st = /* @__PURE__ */ new WeakMap();
let $t = class {
  constructor(t, e, i) {
    if (this._$cssResult$ = !0, i !== Y) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
    this.cssText = t, this.t = e;
  }
  get styleSheet() {
    let t = this.o;
    const e = this.t;
    if (Q && t === void 0) {
      const i = e !== void 0 && e.length === 1;
      i && (t = st.get(e)), t === void 0 && ((this.o = t = new CSSStyleSheet()).replaceSync(this.cssText), i && st.set(e, t));
    }
    return t;
  }
  toString() {
    return this.cssText;
  }
};
const Pt = (n) => new $t(typeof n == "string" ? n : n + "", void 0, Y), vt = (n, ...t) => {
  const e = n.length === 1 ? n[0] : t.reduce((i, s, a) => i + ((o) => {
    if (o._$cssResult$ === !0) return o.cssText;
    if (typeof o == "number") return o;
    throw Error("Value passed to 'css' function must be a 'css' function result: " + o + ". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.");
  })(s) + n[a + 1], n[0]);
  return new $t(e, n, Y);
}, Tt = (n, t) => {
  if (Q) n.adoptedStyleSheets = t.map((e) => e instanceof CSSStyleSheet ? e : e.styleSheet);
  else for (const e of t) {
    const i = document.createElement("style"), s = O.litNonce;
    s !== void 0 && i.setAttribute("nonce", s), i.textContent = e.cssText, n.appendChild(i);
  }
}, nt = Q ? (n) => n : (n) => n instanceof CSSStyleSheet ? ((t) => {
  let e = "";
  for (const i of t.cssRules) e += i.cssText;
  return Pt(e);
})(n) : n;
const { is: Ut, defineProperty: Dt, getOwnPropertyDescriptor: Ot, getOwnPropertyNames: Rt, getOwnPropertySymbols: Lt, getPrototypeOf: It } = Object, V = globalThis, rt = V.trustedTypes, Ht = rt ? rt.emptyScript : "", Wt = V.reactiveElementPolyfillSupport, N = (n, t) => n, G = { toAttribute(n, t) {
  switch (t) {
    case Boolean:
      n = n ? Ht : null;
      break;
    case Object:
    case Array:
      n = n == null ? n : JSON.stringify(n);
  }
  return n;
}, fromAttribute(n, t) {
  let e = n;
  switch (t) {
    case Boolean:
      e = n !== null;
      break;
    case Number:
      e = n === null ? null : Number(n);
      break;
    case Object:
    case Array:
      try {
        e = JSON.parse(n);
      } catch {
        e = null;
      }
  }
  return e;
} }, bt = (n, t) => !Ut(n, t), at = { attribute: !0, type: String, converter: G, reflect: !1, useDefault: !1, hasChanged: bt };
Symbol.metadata ??= /* @__PURE__ */ Symbol("metadata"), V.litPropertyMetadata ??= /* @__PURE__ */ new WeakMap();
let z = class extends HTMLElement {
  static addInitializer(t) {
    this._$Ei(), (this.l ??= []).push(t);
  }
  static get observedAttributes() {
    return this.finalize(), this._$Eh && [...this._$Eh.keys()];
  }
  static createProperty(t, e = at) {
    if (e.state && (e.attribute = !1), this._$Ei(), this.prototype.hasOwnProperty(t) && ((e = Object.create(e)).wrapped = !0), this.elementProperties.set(t, e), !e.noAccessor) {
      const i = /* @__PURE__ */ Symbol(), s = this.getPropertyDescriptor(t, i, e);
      s !== void 0 && Dt(this.prototype, t, s);
    }
  }
  static getPropertyDescriptor(t, e, i) {
    const { get: s, set: a } = Ot(this.prototype, t) ?? { get() {
      return this[e];
    }, set(o) {
      this[e] = o;
    } };
    return { get: s, set(o) {
      const p = s?.call(this);
      a?.call(this, o), this.requestUpdate(t, p, i);
    }, configurable: !0, enumerable: !0 };
  }
  static getPropertyOptions(t) {
    return this.elementProperties.get(t) ?? at;
  }
  static _$Ei() {
    if (this.hasOwnProperty(N("elementProperties"))) return;
    const t = It(this);
    t.finalize(), t.l !== void 0 && (this.l = [...t.l]), this.elementProperties = new Map(t.elementProperties);
  }
  static finalize() {
    if (this.hasOwnProperty(N("finalized"))) return;
    if (this.finalized = !0, this._$Ei(), this.hasOwnProperty(N("properties"))) {
      const e = this.properties, i = [...Rt(e), ...Lt(e)];
      for (const s of i) this.createProperty(s, e[s]);
    }
    const t = this[Symbol.metadata];
    if (t !== null) {
      const e = litPropertyMetadata.get(t);
      if (e !== void 0) for (const [i, s] of e) this.elementProperties.set(i, s);
    }
    this._$Eh = /* @__PURE__ */ new Map();
    for (const [e, i] of this.elementProperties) {
      const s = this._$Eu(e, i);
      s !== void 0 && this._$Eh.set(s, e);
    }
    this.elementStyles = this.finalizeStyles(this.styles);
  }
  static finalizeStyles(t) {
    const e = [];
    if (Array.isArray(t)) {
      const i = new Set(t.flat(1 / 0).reverse());
      for (const s of i) e.unshift(nt(s));
    } else t !== void 0 && e.push(nt(t));
    return e;
  }
  static _$Eu(t, e) {
    const i = e.attribute;
    return i === !1 ? void 0 : typeof i == "string" ? i : typeof t == "string" ? t.toLowerCase() : void 0;
  }
  constructor() {
    super(), this._$Ep = void 0, this.isUpdatePending = !1, this.hasUpdated = !1, this._$Em = null, this._$Ev();
  }
  _$Ev() {
    this._$ES = new Promise((t) => this.enableUpdating = t), this._$AL = /* @__PURE__ */ new Map(), this._$E_(), this.requestUpdate(), this.constructor.l?.forEach((t) => t(this));
  }
  addController(t) {
    (this._$EO ??= /* @__PURE__ */ new Set()).add(t), this.renderRoot !== void 0 && this.isConnected && t.hostConnected?.();
  }
  removeController(t) {
    this._$EO?.delete(t);
  }
  _$E_() {
    const t = /* @__PURE__ */ new Map(), e = this.constructor.elementProperties;
    for (const i of e.keys()) this.hasOwnProperty(i) && (t.set(i, this[i]), delete this[i]);
    t.size > 0 && (this._$Ep = t);
  }
  createRenderRoot() {
    const t = this.shadowRoot ?? this.attachShadow(this.constructor.shadowRootOptions);
    return Tt(t, this.constructor.elementStyles), t;
  }
  connectedCallback() {
    this.renderRoot ??= this.createRenderRoot(), this.enableUpdating(!0), this._$EO?.forEach((t) => t.hostConnected?.());
  }
  enableUpdating(t) {
  }
  disconnectedCallback() {
    this._$EO?.forEach((t) => t.hostDisconnected?.());
  }
  attributeChangedCallback(t, e, i) {
    this._$AK(t, i);
  }
  _$ET(t, e) {
    const i = this.constructor.elementProperties.get(t), s = this.constructor._$Eu(t, i);
    if (s !== void 0 && i.reflect === !0) {
      const a = (i.converter?.toAttribute !== void 0 ? i.converter : G).toAttribute(e, i.type);
      this._$Em = t, a == null ? this.removeAttribute(s) : this.setAttribute(s, a), this._$Em = null;
    }
  }
  _$AK(t, e) {
    const i = this.constructor, s = i._$Eh.get(t);
    if (s !== void 0 && this._$Em !== s) {
      const a = i.getPropertyOptions(s), o = typeof a.converter == "function" ? { fromAttribute: a.converter } : a.converter?.fromAttribute !== void 0 ? a.converter : G;
      this._$Em = s;
      const p = o.fromAttribute(e, a.type);
      this[s] = p ?? this._$Ej?.get(s) ?? p, this._$Em = null;
    }
  }
  requestUpdate(t, e, i, s = !1, a) {
    if (t !== void 0) {
      const o = this.constructor;
      if (s === !1 && (a = this[t]), i ??= o.getPropertyOptions(t), !((i.hasChanged ?? bt)(a, e) || i.useDefault && i.reflect && a === this._$Ej?.get(t) && !this.hasAttribute(o._$Eu(t, i)))) return;
      this.C(t, e, i);
    }
    this.isUpdatePending === !1 && (this._$ES = this._$EP());
  }
  C(t, e, { useDefault: i, reflect: s, wrapped: a }, o) {
    i && !(this._$Ej ??= /* @__PURE__ */ new Map()).has(t) && (this._$Ej.set(t, o ?? e ?? this[t]), a !== !0 || o !== void 0) || (this._$AL.has(t) || (this.hasUpdated || i || (e = void 0), this._$AL.set(t, e)), s === !0 && this._$Em !== t && (this._$Eq ??= /* @__PURE__ */ new Set()).add(t));
  }
  async _$EP() {
    this.isUpdatePending = !0;
    try {
      await this._$ES;
    } catch (e) {
      Promise.reject(e);
    }
    const t = this.scheduleUpdate();
    return t != null && await t, !this.isUpdatePending;
  }
  scheduleUpdate() {
    return this.performUpdate();
  }
  performUpdate() {
    if (!this.isUpdatePending) return;
    if (!this.hasUpdated) {
      if (this.renderRoot ??= this.createRenderRoot(), this._$Ep) {
        for (const [s, a] of this._$Ep) this[s] = a;
        this._$Ep = void 0;
      }
      const i = this.constructor.elementProperties;
      if (i.size > 0) for (const [s, a] of i) {
        const { wrapped: o } = a, p = this[s];
        o !== !0 || this._$AL.has(s) || p === void 0 || this.C(s, void 0, a, p);
      }
    }
    let t = !1;
    const e = this._$AL;
    try {
      t = this.shouldUpdate(e), t ? (this.willUpdate(e), this._$EO?.forEach((i) => i.hostUpdate?.()), this.update(e)) : this._$EM();
    } catch (i) {
      throw t = !1, this._$EM(), i;
    }
    t && this._$AE(e);
  }
  willUpdate(t) {
  }
  _$AE(t) {
    this._$EO?.forEach((e) => e.hostUpdated?.()), this.hasUpdated || (this.hasUpdated = !0, this.firstUpdated(t)), this.updated(t);
  }
  _$EM() {
    this._$AL = /* @__PURE__ */ new Map(), this.isUpdatePending = !1;
  }
  get updateComplete() {
    return this.getUpdateComplete();
  }
  getUpdateComplete() {
    return this._$ES;
  }
  shouldUpdate(t) {
    return !0;
  }
  update(t) {
    this._$Eq &&= this._$Eq.forEach((e) => this._$ET(e, this[e])), this._$EM();
  }
  updated(t) {
  }
  firstUpdated(t) {
  }
};
z.elementStyles = [], z.shadowRootOptions = { mode: "open" }, z[N("elementProperties")] = /* @__PURE__ */ new Map(), z[N("finalized")] = /* @__PURE__ */ new Map(), Wt?.({ ReactiveElement: z }), (V.reactiveElementVersions ??= []).push("2.1.2");
const X = globalThis, ot = (n) => n, R = X.trustedTypes, ct = R ? R.createPolicy("lit-html", { createHTML: (n) => n }) : void 0, wt = "$lit$", b = `lit$${Math.random().toFixed(9).slice(2)}$`, At = "?" + b, Bt = `<${At}>`, E = document, P = () => E.createComment(""), T = (n) => n === null || typeof n != "object" && typeof n != "function", tt = Array.isArray, Vt = (n) => tt(n) || typeof n?.[Symbol.iterator] == "function", j = `[\x20\t\n\f\r]`, q = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g, ht = /-->/g, lt = />/g, x = RegExp(`>|${j}(?:([^\\s"'>=/]+)(${j}*=${j}*(?:[^\x20\t\n\f\r"'\`<>=]|("|')|))|$)`, "g"), dt = /'/g, ut = /"/g, xt = /^(?:script|style|textarea|title)$/i, Ft = (n) => (t, ...e) => ({ _$litType$: n, strings: t, values: e }), l = Ft(1), M = /* @__PURE__ */ Symbol.for("lit-noChange"), c = /* @__PURE__ */ Symbol.for("lit-nothing"), pt = /* @__PURE__ */ new WeakMap(), k = E.createTreeWalker(E, 129);
function kt(n, t) {
  if (!tt(n) || !n.hasOwnProperty("raw")) throw Error("invalid template strings array");
  return ct !== void 0 ? ct.createHTML(t) : t;
}
const jt = (n, t) => {
  const e = n.length - 1, i = [];
  let s, a = t === 2 ? "<svg>" : t === 3 ? "<math>" : "", o = q;
  for (let p = 0; p < e; p++) {
    const h = n[p];
    let _, m, d = -1, g = 0;
    for (; g < h.length && (o.lastIndex = g, m = o.exec(h), m !== null); ) g = o.lastIndex, o === q ? m[1] === "!--" ? o = ht : m[1] !== void 0 ? o = lt : m[2] !== void 0 ? (xt.test(m[2]) && (s = RegExp("</" + m[2], "g")), o = x) : m[3] !== void 0 && (o = x) : o === x ? m[0] === ">" ? (o = s ?? q, d = -1) : m[1] === void 0 ? d = -2 : (d = o.lastIndex - m[2].length, _ = m[1], o = m[3] === void 0 ? x : m[3] === '"' ? ut : dt) : o === ut || o === dt ? o = x : o === ht || o === lt ? o = q : (o = x, s = void 0);
    const y = o === x && n[p + 1].startsWith("/>") ? " " : "";
    a += o === q ? h + Bt : d >= 0 ? (i.push(_), h.slice(0, d) + wt + h.slice(d) + b + y) : h + b + (d === -2 ? p : y);
  }
  return [kt(n, a + (n[e] || "<?>") + (t === 2 ? "</svg>" : t === 3 ? "</math>" : "")), i];
};
class U {
  constructor({ strings: t, _$litType$: e }, i) {
    let s;
    this.parts = [];
    let a = 0, o = 0;
    const p = t.length - 1, h = this.parts, [_, m] = jt(t, e);
    if (this.el = U.createElement(_, i), k.currentNode = this.el.content, e === 2 || e === 3) {
      const d = this.el.content.firstChild;
      d.replaceWith(...d.childNodes);
    }
    for (; (s = k.nextNode()) !== null && h.length < p; ) {
      if (s.nodeType === 1) {
        if (s.hasAttributes()) for (const d of s.getAttributeNames()) if (d.endsWith(wt)) {
          const g = m[o++], y = s.getAttribute(d).split(b), A = /([.?@])?(.*)/.exec(g);
          h.push({ type: 1, index: a, name: A[2], strings: y, ctor: A[1] === "." ? Gt : A[1] === "?" ? Kt : A[1] === "@" ? Jt : F }), s.removeAttribute(d);
        } else d.startsWith(b) && (h.push({ type: 6, index: a }), s.removeAttribute(d));
        if (xt.test(s.tagName)) {
          const d = s.textContent.split(b), g = d.length - 1;
          if (g > 0) {
            s.textContent = R ? R.emptyScript : "";
            for (let y = 0; y < g; y++) s.append(d[y], P()), k.nextNode(), h.push({ type: 2, index: ++a });
            s.append(d[g], P());
          }
        }
      } else if (s.nodeType === 8) if (s.data === At) h.push({ type: 2, index: a });
      else {
        let d = -1;
        for (; (d = s.data.indexOf(b, d + 1)) !== -1; ) h.push({ type: 7, index: a }), d += b.length - 1;
      }
      a++;
    }
  }
  static createElement(t, e) {
    const i = E.createElement("template");
    return i.innerHTML = t, i;
  }
}
function C(n, t, e = n, i) {
  if (t === M) return t;
  let s = i !== void 0 ? e._$Co?.[i] : e._$Cl;
  const a = T(t) ? void 0 : t._$litDirective$;
  return s?.constructor !== a && (s?._$AO?.(!1), a === void 0 ? s = void 0 : (s = new a(n), s._$AT(n, e, i)), i !== void 0 ? (e._$Co ??= [])[i] = s : e._$Cl = s), s !== void 0 && (t = C(n, s._$AS(n, t.values), s, i)), t;
}
class Zt {
  constructor(t, e) {
    this._$AV = [], this._$AN = void 0, this._$AD = t, this._$AM = e;
  }
  get parentNode() {
    return this._$AM.parentNode;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  u(t) {
    const { el: { content: e }, parts: i } = this._$AD, s = (t?.creationScope ?? E).importNode(e, !0);
    k.currentNode = s;
    let a = k.nextNode(), o = 0, p = 0, h = i[0];
    for (; h !== void 0; ) {
      if (o === h.index) {
        let _;
        h.type === 2 ? _ = new D(a, a.nextSibling, this, t) : h.type === 1 ? _ = new h.ctor(a, h.name, h.strings, this, t) : h.type === 6 && (_ = new Qt(a, this, t)), this._$AV.push(_), h = i[++p];
      }
      o !== h?.index && (a = k.nextNode(), o++);
    }
    return k.currentNode = E, s;
  }
  p(t) {
    let e = 0;
    for (const i of this._$AV) i !== void 0 && (i.strings !== void 0 ? (i._$AI(t, i, e), e += i.strings.length - 2) : i._$AI(t[e])), e++;
  }
}
class D {
  get _$AU() {
    return this._$AM?._$AU ?? this._$Cv;
  }
  constructor(t, e, i, s) {
    this.type = 2, this._$AH = c, this._$AN = void 0, this._$AA = t, this._$AB = e, this._$AM = i, this.options = s, this._$Cv = s?.isConnected ?? !0;
  }
  get parentNode() {
    let t = this._$AA.parentNode;
    const e = this._$AM;
    return e !== void 0 && t?.nodeType === 11 && (t = e.parentNode), t;
  }
  get startNode() {
    return this._$AA;
  }
  get endNode() {
    return this._$AB;
  }
  _$AI(t, e = this) {
    t = C(this, t, e), T(t) ? t === c || t == null || t === "" ? (this._$AH !== c && this._$AR(), this._$AH = c) : t !== this._$AH && t !== M && this._(t) : t._$litType$ !== void 0 ? this.$(t) : t.nodeType !== void 0 ? this.T(t) : Vt(t) ? this.k(t) : this._(t);
  }
  O(t) {
    return this._$AA.parentNode.insertBefore(t, this._$AB);
  }
  T(t) {
    this._$AH !== t && (this._$AR(), this._$AH = this.O(t));
  }
  _(t) {
    this._$AH !== c && T(this._$AH) ? this._$AA.nextSibling.data = t : this.T(E.createTextNode(t)), this._$AH = t;
  }
  $(t) {
    const { values: e, _$litType$: i } = t, s = typeof i == "number" ? this._$AC(t) : (i.el === void 0 && (i.el = U.createElement(kt(i.h, i.h[0]), this.options)), i);
    if (this._$AH?._$AD === s) this._$AH.p(e);
    else {
      const a = new Zt(s, this), o = a.u(this.options);
      a.p(e), this.T(o), this._$AH = a;
    }
  }
  _$AC(t) {
    let e = pt.get(t.strings);
    return e === void 0 && pt.set(t.strings, e = new U(t)), e;
  }
  k(t) {
    tt(this._$AH) || (this._$AH = [], this._$AR());
    const e = this._$AH;
    let i, s = 0;
    for (const a of t) s === e.length ? e.push(i = new D(this.O(P()), this.O(P()), this, this.options)) : i = e[s], i._$AI(a), s++;
    s < e.length && (this._$AR(i && i._$AB.nextSibling, s), e.length = s);
  }
  _$AR(t = this._$AA.nextSibling, e) {
    for (this._$AP?.(!1, !0, e); t !== this._$AB; ) {
      const i = ot(t).nextSibling;
      ot(t).remove(), t = i;
    }
  }
  setConnected(t) {
    this._$AM === void 0 && (this._$Cv = t, this._$AP?.(t));
  }
}
class F {
  get tagName() {
    return this.element.tagName;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  constructor(t, e, i, s, a) {
    this.type = 1, this._$AH = c, this._$AN = void 0, this.element = t, this.name = e, this._$AM = s, this.options = a, i.length > 2 || i[0] !== "" || i[1] !== "" ? (this._$AH = Array(i.length - 1).fill(new String()), this.strings = i) : this._$AH = c;
  }
  _$AI(t, e = this, i, s) {
    const a = this.strings;
    let o = !1;
    if (a === void 0) t = C(this, t, e, 0), o = !T(t) || t !== this._$AH && t !== M, o && (this._$AH = t);
    else {
      const p = t;
      let h, _;
      for (t = a[0], h = 0; h < a.length - 1; h++) _ = C(this, p[i + h], e, h), _ === M && (_ = this._$AH[h]), o ||= !T(_) || _ !== this._$AH[h], _ === c ? t = c : t !== c && (t += (_ ?? "") + a[h + 1]), this._$AH[h] = _;
    }
    o && !s && this.j(t);
  }
  j(t) {
    t === c ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, t ?? "");
  }
}
class Gt extends F {
  constructor() {
    super(...arguments), this.type = 3;
  }
  j(t) {
    this.element[this.name] = t === c ? void 0 : t;
  }
}
class Kt extends F {
  constructor() {
    super(...arguments), this.type = 4;
  }
  j(t) {
    this.element.toggleAttribute(this.name, !!t && t !== c);
  }
}
class Jt extends F {
  constructor(t, e, i, s, a) {
    super(t, e, i, s, a), this.type = 5;
  }
  _$AI(t, e = this) {
    if ((t = C(this, t, e, 0) ?? c) === M) return;
    const i = this._$AH, s = t === c && i !== c || t.capture !== i.capture || t.once !== i.once || t.passive !== i.passive, a = t !== c && (i === c || s);
    s && this.element.removeEventListener(this.name, this, i), a && this.element.addEventListener(this.name, this, t), this._$AH = t;
  }
  handleEvent(t) {
    typeof this._$AH == "function" ? this._$AH.call(this.options?.host ?? this.element, t) : this._$AH.handleEvent(t);
  }
}
class Qt {
  constructor(t, e, i) {
    this.element = t, this.type = 6, this._$AN = void 0, this._$AM = e, this.options = i;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  _$AI(t) {
    C(this, t);
  }
}
const Yt = X.litHtmlPolyfillSupport;
Yt?.(U, D), (X.litHtmlVersions ??= []).push("3.3.3");
const Xt = (n, t, e) => {
  const i = e?.renderBefore ?? t;
  let s = i._$litPart$;
  if (s === void 0) {
    const a = e?.renderBefore ?? null;
    i._$litPart$ = s = new D(t.insertBefore(P(), a), a, void 0, e ?? {});
  }
  return s._$AI(n), s;
};
const et = globalThis;
class S extends z {
  constructor() {
    super(...arguments), this.renderOptions = { host: this }, this._$Do = void 0;
  }
  createRenderRoot() {
    const t = super.createRenderRoot();
    return this.renderOptions.renderBefore ??= t.firstChild, t;
  }
  update(t) {
    const e = this.render();
    this.hasUpdated || (this.renderOptions.isConnected = this.isConnected), super.update(t), this._$Do = Xt(e, this.renderRoot, this.renderOptions);
  }
  connectedCallback() {
    super.connectedCallback(), this._$Do?.setConnected(!0);
  }
  disconnectedCallback() {
    super.disconnectedCallback(), this._$Do?.setConnected(!1);
  }
  render() {
    return M;
  }
}
S._$litElement$ = !0, S.finalized = !0, et.litElementHydrateSupport?.({ LitElement: S });
const te = et.litElementPolyfillSupport;
te?.({ LitElement: S });
(et.litElementVersions ??= []).push("4.2.2");
const St = "irrigation_manager", ee = "create_manual", ie = /* @__PURE__ */ new Set(["unknown", "unavailable"]);
function u(n, t) {
  return t ? n.states[t] : void 0;
}
function L(n) {
  return !!(n && !ie.has(n.state));
}
function f(n, t) {
  const e = n?.attributes[t];
  return typeof e == "string" && e ? e : void 0;
}
function _t(n, t) {
  const e = n?.attributes[t];
  return typeof e == "number" && Number.isFinite(e) ? e : void 0;
}
function Z(n, t) {
  if (!t || f(n, "zone_subentry_id") !== t)
    return;
  const e = f(n, "request_id"), i = f(n, "execution_id");
  return e || i ? { requestId: e, executionId: i } : void 0;
}
function Et(n) {
  const t = _t(n, "target_value"), e = _t(n, "remaining_value");
  if (!(t === void 0 || e === void 0 || t <= 0))
    return Math.max(0, Math.min(100, (t - e) / t * 100));
}
function zt(n) {
  return {
    idle: "mdi:water-check-outline",
    watering: "mdi:sprinkler-variant",
    soaking: "mdi:timer-sand",
    error: "mdi:alert-circle-outline",
    safety_lock: "mdi:lock-alert-outline",
    emergency_stop: "mdi:alert-octagon",
    unavailable: "mdi:cloud-alert-outline",
    unknown: "mdi:help-circle-outline",
    on: "mdi:check-circle-outline",
    off: "mdi:minus-circle-outline"
  }[n] ?? "mdi:information-outline";
}
function se(n, t) {
  n.dispatchEvent(
    new CustomEvent("config-changed", {
      detail: { config: t },
      bubbles: !0,
      composed: !0
    })
  );
}
const Mt = {
  en: {
    overview: "Irrigation overview",
    zone: "Irrigation zone",
    unavailable: "Unavailable",
    unknown: "Unknown",
    missing: "Entity not found",
    idle: "Idle",
    watering: "Watering",
    soaking: "Soaking",
    error: "Error",
    safety_lock: "Safety lock",
    emergency_stop: "Emergency stop",
    active_zone: "Active zone",
    active: "Active irrigation",
    balance: "Water balance",
    progress: "Progress",
    dose: "Current dose",
    pending: "Open requests",
    next: "Next irrigation",
    today: "Today",
    month: "This month",
    model_quality: "Model quality",
    stop: "Stop",
    emergency: "Emergency stop",
    confirm_stop: "Stop the current irrigation?",
    stop_skip: "Stop and skip once",
    confirm_stop_skip: "Stop this irrigation and suppress the current automatic opportunity?",
    confirm_emergency: "Trigger emergency stop and lock the installation?",
    action_failed: "Action failed",
    configuration_error: "The selected entity does not expose the identifiers required by this action.",
    automation_needed: "Irrigation needed",
    automation_not_needed: "No irrigation needed",
    locked: "Locked",
    unlocked: "Ready",
    water_balance: "Water balance",
    target: "Automatic target",
    explanation: "Planning explanation",
    next_window: "Next window",
    total: "Total consumption",
    recent: "Recent irrigation",
    last_delivered: "Delivered",
    last_duration: "Duration",
    quality: "Measurement quality",
    manual: "Manual irrigation",
    amount: "Amount",
    duration: "Duration",
    hard_limit: "Maximum duration",
    liters: "L",
    seconds: "s",
    create: "Create request",
    start: "Start now",
    pause: "Pause",
    resume: "Resume",
    warning_estimated: "The latest amount was estimated.",
    warning_unknown: "No reliable measurement is available.",
    invalid_target: "Enter a value greater than zero.",
    hard_limit_required: "A maximum duration is required for amount control.",
    status: "Status",
    display: "Display",
    compact: "Compact",
    detailed: "Detailed",
    metrics: "Visible metrics",
    actions: "Visible actions",
    required_entity: "Required entity",
    optional_entities: "Optional entities",
    amount_mode: "Amount controlled",
    duration_mode: "Time controlled",
    yes: "Yes",
    no: "No",
    measured: "Measured",
    estimated: "Estimated",
    automatic_due: "Water demand reached",
    automation_disabled: "Automatic irrigation disabled",
    below_threshold: "Water demand below threshold",
    no_window: "No watering window available",
    winter_lock: "Winter lock active",
    maintenance_active: "Maintenance test active",
    maintenance_due: "Maintenance due",
    automatic_suspended: "Automatic irrigation suspended until",
    suspend_24h: "Suspend 24 h",
    resume_automatic: "Resume automatic irrigation",
    confirm_suspend: "Suspend automatic irrigation for 24 hours?",
    confirm_resume: "Resume automatic irrigation now?",
    archived: "Archived",
    archive: "Archive",
    restore: "Restore",
    confirm_archive: "Archive this zone? The installation must be completely idle.",
    flow_warning: "Flow deviation",
    coverage: "Demand coverage",
    expected_flow: "Expected flow",
    actual_flow: "Actual flow",
    flow_deviation: "Flow deviation",
    history: "History"
  },
  de: {
    overview: "Bewässerungsübersicht",
    zone: "Bewässerungszone",
    unavailable: "Nicht verfügbar",
    unknown: "Unbekannt",
    missing: "Entity nicht gefunden",
    idle: "Bereit",
    watering: "Bewässerung läuft",
    soaking: "Sickerpause",
    error: "Fehler",
    safety_lock: "Sicherheitssperre",
    emergency_stop: "Not-Aus aktiv",
    active_zone: "Aktive Zone",
    active: "Aktive Bewässerung",
    balance: "Wasserbilanz",
    progress: "Fortschritt",
    dose: "Aktuelle Teilgabe",
    pending: "Offene Aufträge",
    next: "Nächste Bewässerung",
    today: "Heute",
    month: "Dieser Monat",
    model_quality: "Modellqualität",
    stop: "Stoppen",
    emergency: "Not-Aus",
    confirm_stop: "Aktuelle Bewässerung stoppen?",
    stop_skip: "Stoppen und einmal überspringen",
    confirm_stop_skip: "Diese Bewässerung stoppen und die aktuelle automatische Gelegenheit unterdrücken?",
    confirm_emergency: "Not-Aus auslösen und die Anlage sperren?",
    action_failed: "Aktion fehlgeschlagen",
    configuration_error: "Die gewählte Entity stellt die für diese Aktion benötigten Kennungen nicht bereit.",
    automation_needed: "Bewässerung erforderlich",
    automation_not_needed: "Keine Bewässerung erforderlich",
    locked: "Gesperrt",
    unlocked: "Bereit",
    water_balance: "Wasserbilanz",
    target: "Automatisches Ziel",
    explanation: "Planungsbegründung",
    next_window: "Nächstes Fenster",
    total: "Gesamtverbrauch",
    recent: "Letzte Bewässerung",
    last_delivered: "Geliefert",
    last_duration: "Dauer",
    quality: "Messqualität",
    manual: "Manuelle Bewässerung",
    amount: "Menge",
    duration: "Dauer",
    hard_limit: "Maximale Dauer",
    liters: "L",
    seconds: "s",
    create: "Auftrag erstellen",
    start: "Sofort starten",
    pause: "Pausieren",
    resume: "Fortsetzen",
    warning_estimated: "Die letzte Menge wurde geschätzt.",
    warning_unknown: "Es ist keine verlässliche Messung verfügbar.",
    invalid_target: "Einen Wert größer als null eingeben.",
    hard_limit_required: "Für die Mengensteuerung ist eine maximale Dauer erforderlich.",
    status: "Status",
    display: "Darstellung",
    compact: "Kompakt",
    detailed: "Ausführlich",
    metrics: "Sichtbare Kennzahlen",
    actions: "Sichtbare Aktionen",
    required_entity: "Erforderliche Entity",
    optional_entities: "Optionale Entities",
    amount_mode: "Mengengesteuert",
    duration_mode: "Zeitgesteuert",
    yes: "Ja",
    no: "Nein",
    measured: "Gemessen",
    estimated: "Geschätzt",
    automatic_due: "Wasserbedarf erreicht",
    automation_disabled: "Automatikfreigabe fehlt",
    below_threshold: "Wasserbedarf unter Grenzwert",
    no_window: "Kein Bewässerungsfenster verfügbar",
    winter_lock: "Wintersperre aktiv",
    maintenance_active: "Wartungstest aktiv",
    maintenance_due: "Wartung fällig",
    automatic_suspended: "Automatik ausgesetzt bis",
    suspend_24h: "24 h aussetzen",
    resume_automatic: "Automatik fortsetzen",
    confirm_suspend: "Automatik für 24 Stunden aussetzen?",
    confirm_resume: "Automatik jetzt fortsetzen?",
    archived: "Archiviert",
    archive: "Archivieren",
    restore: "Wiederherstellen",
    confirm_archive: "Diese Zone archivieren? Die Anlage muss vollständig im Leerlauf sein.",
    flow_warning: "Durchflussabweichung",
    coverage: "Bedarfsdeckung",
    expected_flow: "Erwarteter Durchfluss",
    actual_flow: "Tatsächlicher Durchfluss",
    flow_deviation: "Durchflussabweichung",
    history: "Historie"
  }
};
function r(n, t) {
  const e = n.language?.toLowerCase().startsWith("de") ? "de" : "en";
  return Mt[e][t];
}
function Ct(n, t) {
  return t in Mt.en ? r(n, t) : t.replaceAll("_", " ");
}
function w(n, t) {
  if (!t) return r(n, "missing");
  if (t.state === "unavailable") return r(n, "unavailable");
  if (t.state === "unknown" || t.state === "") return r(n, "unknown");
  if (n.formatEntityState) return n.formatEntityState(t);
  const e = t.attributes.unit_of_measurement;
  return `${Ct(n, t.state)}${e ? ` ${e}` : ""}`;
}
const qt = vt`
  :host { display: block; }
  ha-card { overflow: hidden; color: var(--primary-text-color); }
  .card { padding: 16px; display: grid; gap: 16px; }
  header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  h2, h3 { margin: 0; font-weight: 500; }
  h2 { font-size: 1.25rem; }
  h3 { font-size: 0.95rem; color: var(--secondary-text-color); }
  .hero { display: flex; align-items: center; gap: 12px; min-width: 0; }
  .hero ha-icon { --mdc-icon-size: 32px; color: var(--primary-color); flex: 0 0 auto; }
  .hero strong, .metric strong { display: block; overflow-wrap: anywhere; }
  .secondary { color: var(--secondary-text-color); font-size: 0.875rem; }
  .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; }
  .metric { padding: 10px 12px; border: 1px solid var(--divider-color); border-radius: var(--ha-card-border-radius, 12px); min-width: 0; }
  .metric span { display: block; color: var(--secondary-text-color); font-size: 0.78rem; margin-bottom: 3px; }
  .warning { display: flex; align-items: flex-start; gap: 8px; padding: 10px 12px; border-left: 4px solid var(--warning-color, var(--primary-color)); background: var(--secondary-background-color); border-radius: 4px; }
  .warning.danger { border-left-color: var(--error-color); }
  progress { width: 100%; height: 8px; accent-color: var(--primary-color); }
  .actions { display: flex; flex-wrap: wrap; gap: 8px; }
  button { min-height: 40px; padding: 0 14px; border: 1px solid var(--divider-color); border-radius: 10px; background: var(--card-background-color); color: var(--primary-text-color); font: inherit; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: 7px; }
  button.primary { background: var(--primary-color); border-color: var(--primary-color); color: var(--text-primary-color, white); }
  button.danger { border-color: var(--error-color); color: var(--error-color); }
  button:disabled { opacity: 0.45; cursor: not-allowed; }
  button:focus-visible, input:focus-visible, select:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
  .form-grid { display: grid; grid-template-columns: minmax(130px, 1fr) minmax(110px, 1fr); gap: 10px; align-items: end; }
  label.field { display: grid; gap: 5px; color: var(--secondary-text-color); font-size: 0.8rem; }
  input, select { box-sizing: border-box; width: 100%; min-height: 40px; padding: 8px 10px; color: var(--primary-text-color); background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 8px; font: inherit; }
  .error { color: var(--error-color); font-size: 0.875rem; }
  .compact .details { display: none; }
  @media (max-width: 480px) {
    .card { padding: 14px; }
    .form-grid { grid-template-columns: 1fr; }
    .actions button { flex: 1 1 calc(50% - 8px); }
  }
`, ne = vt`
  :host { display: block; }
  .editor { display: grid; gap: 18px; padding: 8px 0; }
  section { display: grid; gap: 10px; }
  h3 { margin: 0; font-size: 1rem; }
  label.selector { display: grid; gap: 5px; color: var(--secondary-text-color); }
  .checks { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 6px 12px; }
  .check { display: flex; align-items: center; gap: 8px; min-height: 34px; }
  input[type="checkbox"] { width: 18px; height: 18px; accent-color: var(--primary-color); }
  select { min-height: 40px; padding: 8px; color: var(--primary-text-color); background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 8px; }
`, mt = [
  ["status_entity", "Installation status"],
  ["emergency_entity", "Emergency stop"],
  ["lock_entity", "Installation safety lock"],
  ["active_zone_entity", "Active zone / progress"],
  ["dose_entity", "Current dose"],
  ["pending_entity", "Open requests"],
  ["next_entity", "Next irrigation"],
  ["today_consumption_entity", "Today's consumption"],
  ["month_consumption_entity", "Monthly consumption"],
  ["model_quality_entity", "Model quality"],
  ["winter_entity", "Winter lock"],
  ["maintenance_entity", "Maintenance mode"],
  ["automation_release_entity", "Automatic release"],
  ["maintenance_due_entity", "Maintenance due"]
], gt = [
  ["zone_entity", "Zone total / action identity"],
  ["automation_needed_entity", "Automatic demand"],
  ["safety_lock_entity", "Zone safety lock"],
  ["deficit_entity", "Water deficit"],
  ["target_entity", "Automatic target"],
  ["planning_reason_entity", "Planning explanation"],
  ["next_window_entity", "Next watering window"],
  ["active_zone_entity", "Active zone / progress"],
  ["request_entity", "Current request / dose"],
  ["last_delivered_entity", "Last delivered amount"],
  ["last_duration_entity", "Last duration"],
  ["quality_entity", "Measurement quality"],
  ["status_entity", "Zone status"],
  ["automation_release_entity", "Automatic release"],
  ["archived_entity", "Archived"],
  ["coverage_entity", "Demand coverage"],
  ["expected_flow_entity", "Expected flow"],
  ["actual_flow_entity", "Actual flow"],
  ["flow_deviation_entity", "Flow deviation"],
  ["calculation_entity", "Calculation"]
], re = {
  "Installation status": "Anlagenzustand",
  "Emergency stop": "Not-Aus",
  "Installation safety lock": "Sicherheitssperre der Anlage",
  "Active zone / progress": "Aktive Zone / Fortschritt",
  "Current dose": "Aktuelle Teilgabe",
  "Open requests": "Offene Aufträge",
  "Next irrigation": "Nächste Bewässerung",
  "Today's consumption": "Heutiger Verbrauch",
  "Monthly consumption": "Monatsverbrauch",
  "Model quality": "Modellqualität",
  "Zone total / action identity": "Zonenverbrauch / Aktionskennung",
  "Automatic demand": "Automatischer Bedarf",
  "Zone safety lock": "Sicherheitssperre der Zone",
  "Water deficit": "Wasserdefizit",
  "Automatic target": "Automatisches Ziel",
  "Planning explanation": "Planungsbegründung",
  "Next watering window": "Nächstes Bewässerungsfenster",
  "Current request / dose": "Aktueller Auftrag / Teilgabe",
  "Last delivered amount": "Zuletzt gelieferte Menge",
  "Last duration": "Letzte Dauer",
  "Measurement quality": "Messqualität"
}, ae = ["active", "pending", "next", "today", "month", "quality", "maintenance"], oe = ["stop", "emergency", "suspend", "resume"], ce = ["status", "balance", "next", "total", "recent", "quality", "calculation", "flow", "history"], he = ["create", "start", "pause", "resume", "stop", "stop_skip", "suspend", "resume_auto", "archive", "restore"], H = class H extends S {
  setConfig(t) {
    this._config = { ...t };
  }
  updateValue(t, e) {
    const i = { ...this._config, [t]: e || void 0 };
    e || delete i[t], this._config = i, se(this, i);
  }
  entitySelector(t, e, i) {
    const s = this.hass.language.toLowerCase().startsWith("de") ? re[e] ?? e : e;
    return l`
      <label class="selector">
        <span>${s}${i ? " *" : ""}</span>
        <ha-selector
          .hass=${this.hass}
          .selector=${{ entity: { filter: { integration: "irrigation_manager" } } }}
          .value=${this._config[t] ?? ""}
          @value-changed=${(a) => this.updateValue(t, a.detail.value)}
        ></ha-selector>
      </label>
    `;
  }
  displayMode() {
    return l`
      <label class="selector">
        <span>${r(this.hass, "display")}</span>
        <select
          .value=${this._config.display_mode ?? "detailed"}
          @change=${(t) => this.updateValue("display_mode", t.target.value)}
        >
          <option value="compact">${r(this.hass, "compact")}</option>
          <option value="detailed">${r(this.hass, "detailed")}</option>
        </select>
      </label>
    `;
  }
  choices(t, e) {
    const i = this._config[t] ?? e;
    return l`
      <div class="checks">
        ${e.map(
      (s) => l`
            <label class="check">
              <input
                type="checkbox"
                .checked=${i.includes(s)}
                @change=${(a) => {
        const o = a.target.checked;
        this.updateValue(
          t,
          o ? [...i, s] : i.filter((p) => p !== s)
        );
      }}
              />
              ${r(this.hass, s)}
            </label>
          `
    )}
      </div>
    `;
  }
};
H.styles = ne, H.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 }
};
let I = H;
class le extends I {
  render() {
    return !this.hass || !this._config ? c : l`
      <div class="editor">
        <section>
          <h3>${r(this.hass, "required_entity")}</h3>
          ${this.entitySelector("status_entity", mt[0][1], !0)}
        </section>
        <section>
          <h3>${r(this.hass, "optional_entities")}</h3>
          ${mt.slice(1).map(([t, e]) => this.entitySelector(t, e, !1))}
        </section>
        <section>${this.displayMode()}</section>
        <section>
          <h3>${r(this.hass, "metrics")}</h3>
          ${this.choices("visible_metrics", ae)}
        </section>
        <section>
          <h3>${r(this.hass, "actions")}</h3>
          ${this.choices("visible_actions", oe)}
        </section>
      </div>
    `;
  }
}
class de extends I {
  render() {
    return !this.hass || !this._config ? c : l`
      <div class="editor">
        <section>
          <h3>${r(this.hass, "required_entity")}</h3>
          ${this.entitySelector("zone_entity", gt[0][1], !0)}
        </section>
        <section>
          <h3>${r(this.hass, "optional_entities")}</h3>
          ${gt.slice(1).map(([t, e]) => this.entitySelector(t, e, !1))}
        </section>
        <section>${this.displayMode()}</section>
        <section>
          <h3>${r(this.hass, "metrics")}</h3>
          ${this.choices("visible_metrics", ce)}
        </section>
        <section>
          <h3>${r(this.hass, "actions")}</h3>
          ${this.choices("visible_actions", he)}
        </section>
      </div>
    `;
  }
}
const ft = ["active", "pending", "next", "today", "month", "quality", "maintenance"], ue = ["stop", "emergency", "suspend", "resume"], W = class W extends S {
  constructor() {
    super(...arguments), this._busy = !1;
  }
  static getConfigElement() {
    return document.createElement("irrigation-manager-overview-card-editor");
  }
  static getStubConfig() {
    return { type: "custom:irrigation-manager-overview-card", status_entity: "" };
  }
  setConfig(t) {
    if (!t.status_entity) throw new Error("status_entity is required");
    this._config = { ...t };
  }
  getCardSize() {
    return this._config?.display_mode === "compact" ? 3 : 5;
  }
  metric(t, e, i) {
    return (this._config.visible_metrics ?? ft).includes(t) ? l`<div class="metric"><span>${e}</span><strong>${w(this.hass, i)}</strong></div>` : c;
  }
  async call(t, e, i = {}) {
    if (!window.confirm(e)) return;
    const s = u(this.hass, this._config.status_entity), a = f(s, "config_entry_id");
    if (!a) {
      this._error = r(this.hass, "configuration_error");
      return;
    }
    this._busy = !0, this._error = void 0;
    try {
      await this.hass.callService(St, t, { config_entry_id: a, ...i });
    } catch (o) {
      this._error = `${r(this.hass, "action_failed")}: ${o instanceof Error ? o.message : String(o)}`;
    } finally {
      this._busy = !1;
    }
  }
  render() {
    if (!this.hass || !this._config) return c;
    const t = u(this.hass, this._config.status_entity), e = u(this.hass, this._config.emergency_entity), i = u(this.hass, this._config.lock_entity), s = u(this.hass, this._config.winter_entity), a = u(this.hass, this._config.maintenance_entity), o = u(this.hass, this._config.automation_release_entity), p = u(this.hass, this._config.active_zone_entity), h = Et(p), _ = this._config.visible_actions ?? ue, m = t?.state ?? "unavailable", d = e?.state === "on" || i?.state === "on";
    return l`
      <ha-card>
        <div class="card ${this._config.display_mode === "compact" ? "compact" : ""}">
          <header>
            <div class="hero">
              <ha-icon .icon=${zt(m)}></ha-icon>
              <div>
                <h2>${this._config.name ?? r(this.hass, "overview")}</h2>
                <strong>${L(t) ? Ct(this.hass, t.state) : w(this.hass, t)}</strong>
              </div>
            </div>
          </header>

          ${d ? l`<div class="warning danger"><ha-icon icon="mdi:lock-alert-outline"></ha-icon><span>${e?.state === "on" ? r(this.hass, "emergency_stop") : r(this.hass, "safety_lock")}${f(i, "reason") ? `: ${f(i, "reason")}` : ""}</span></div>` : c}
          ${s?.state === "on" ? l`<div class="warning"><ha-icon icon="mdi:snowflake-alert"></ha-icon><span>${r(this.hass, "winter_lock")}</span></div>` : c}
          ${a?.state === "on" ? l`<div class="warning"><ha-icon icon="mdi:wrench-clock"></ha-icon><span>${r(this.hass, "maintenance_active")}</span></div>` : c}
          ${o?.state === "off" && f(o, "suspended_until") ? l`<div class="warning"><ha-icon icon="mdi:calendar-clock"></ha-icon><span>${r(this.hass, "automatic_suspended")}: ${f(o, "suspended_until")}</span></div>` : c}

          ${(this._config.visible_metrics ?? ft).includes("active") && p ? l`
                <section>
                  <h3>${r(this.hass, "active_zone")}</h3>
                  <strong>${w(this.hass, p)}</strong>
                  ${this._config.dose_entity ? l`<div class="secondary">${r(this.hass, "dose")}: ${w(this.hass, u(this.hass, this._config.dose_entity))}</div>` : c}
                  ${h === void 0 ? c : l`<div class="secondary">${r(this.hass, "progress")}: ${Math.round(h)}%</div><progress max="100" .value=${h} aria-label=${r(this.hass, "progress")}></progress>`}
                </section>
              ` : c}

          <div class="metrics details">
            ${this.metric("pending", r(this.hass, "pending"), u(this.hass, this._config.pending_entity))}
            ${this.metric("next", r(this.hass, "next"), u(this.hass, this._config.next_entity))}
            ${this.metric("today", r(this.hass, "today"), u(this.hass, this._config.today_consumption_entity))}
            ${this.metric("month", r(this.hass, "month"), u(this.hass, this._config.month_consumption_entity))}
            ${this.metric("quality", r(this.hass, "model_quality"), u(this.hass, this._config.model_quality_entity))}
            ${this.metric("maintenance", r(this.hass, "maintenance_due"), u(this.hass, this._config.maintenance_due_entity))}
          </div>

          ${this._error ? l`<div class="error" role="alert">${this._error}</div>` : c}
          <div class="actions">
            ${_.includes("stop") ? l`<button class="danger" ?disabled=${this._busy || !L(t)} @click=${() => this.call("stop", r(this.hass, "confirm_stop"))}><ha-icon icon="mdi:stop-circle-outline"></ha-icon>${r(this.hass, "stop")}</button>` : c}
            ${_.includes("emergency") ? l`<button class="danger" ?disabled=${this._busy} @click=${() => this.call("emergency_stop", r(this.hass, "confirm_emergency"))}><ha-icon icon="mdi:alert-octagon-outline"></ha-icon>${r(this.hass, "emergency")}</button>` : c}
            ${_.includes("suspend") ? l`<button ?disabled=${this._busy} @click=${() => this.call("suspend_automatic", r(this.hass, "confirm_suspend"), { until: new Date(Date.now() + 864e5).toISOString() })}><ha-icon icon="mdi:calendar-clock"></ha-icon>${r(this.hass, "suspend_24h")}</button>` : c}
            ${_.includes("resume") ? l`<button ?disabled=${this._busy} @click=${() => this.call("resume_automatic", r(this.hass, "confirm_resume"))}><ha-icon icon="mdi:calendar-check"></ha-icon>${r(this.hass, "resume_automatic")}</button>` : c}
          </div>
        </div>
      </ha-card>
    `;
  }
};
W.styles = qt, W.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 },
  _busy: { state: !0 },
  _error: { state: !0 }
};
let K = W;
const yt = ["status", "balance", "next", "total", "recent", "quality", "calculation", "flow", "history"], pe = ["create", "start", "pause", "resume", "stop", "stop_skip", "suspend", "resume_auto", "archive", "restore"], B = class B extends S {
  constructor() {
    super(...arguments), this._targetMode = "duration", this._targetValue = 600, this._hardLimit = 3600, this._busy = !1;
  }
  static getConfigElement() {
    return document.createElement("irrigation-manager-zone-card-editor");
  }
  static getStubConfig() {
    return { type: "custom:irrigation-manager-zone-card", zone_entity: "" };
  }
  setConfig(t) {
    if (!t.zone_entity) throw new Error("zone_entity is required");
    this._config = { ...t };
  }
  getCardSize() {
    return this._config?.display_mode === "compact" ? 4 : 7;
  }
  metric(t, e, i) {
    return (this._config.visible_metrics ?? yt).includes(t) ? l`<div class="metric"><span>${e}</span><strong>${w(this.hass, i)}</strong></div>` : c;
  }
  context() {
    const t = u(this.hass, this._config.zone_entity), e = f(t, "config_entry_id"), i = f(t, "zone_subentry_id");
    return e && i ? { config_entry_id: e, zone_subentry_id: i } : void 0;
  }
  async perform(t, e, i) {
    if (!(i && !window.confirm(i))) {
      this._busy = !0, this._error = void 0;
      try {
        await this.hass.callService(St, t, e);
      } catch (s) {
        this._error = `${r(this.hass, "action_failed")}: ${s instanceof Error ? s.message : String(s)}`;
      } finally {
        this._busy = !1;
      }
    }
  }
  async request() {
    const t = this.context();
    if (!t) {
      this._error = r(this.hass, "configuration_error");
      return;
    }
    if (!Number.isFinite(this._targetValue) || this._targetValue <= 0) {
      this._error = r(this.hass, "invalid_target");
      return;
    }
    if (this._targetMode === "amount" && (!Number.isFinite(this._hardLimit) || this._hardLimit <= 0)) {
      this._error = r(this.hass, "hard_limit_required");
      return;
    }
    const e = this._targetMode === "duration" ? { duration: this._targetValue } : { amount: this._targetValue, hard_time_limit: this._hardLimit };
    await this.perform(ee, { ...t, ...e });
  }
  async requestAction(t) {
    const e = this.context(), i = u(this.hass, this._config.request_entity), s = Z(i, e?.zone_subentry_id);
    if (!e || !s?.requestId) {
      this._error = r(this.hass, "configuration_error");
      return;
    }
    await this.perform(t, {
      config_entry_id: e.config_entry_id,
      request_id: s.requestId
    });
  }
  async stop(t = !1) {
    const e = this.context(), i = u(this.hass, this._config.request_entity), s = Z(i, e?.zone_subentry_id);
    if (!e || !s) {
      this._error = r(this.hass, "configuration_error");
      return;
    }
    const a = s.executionId ? { execution_id: s.executionId } : { request_id: s.requestId };
    await this.perform(
      t ? "stop_and_skip" : "stop",
      { config_entry_id: e.config_entry_id, ...a },
      r(this.hass, t ? "confirm_stop_skip" : "confirm_stop")
    );
  }
  render() {
    if (!this.hass || !this._config) return c;
    const t = u(this.hass, this._config.zone_entity), e = u(this.hass, this._config.automation_needed_entity), i = u(this.hass, this._config.safety_lock_entity), s = u(this.hass, this._config.quality_entity), a = u(this.hass, this._config.status_entity), o = u(this.hass, this._config.automation_release_entity), p = u(this.hass, this._config.archived_entity), h = u(this.hass, this._config.flow_deviation_entity), _ = u(this.hass, this._config.active_zone_entity), m = u(this.hass, this._config.request_entity), d = this.context(), g = Z(m, d?.zone_subentry_id), y = Et(_), A = this._config.visible_metrics ?? yt, $ = this._config.visible_actions ?? pe, Nt = this._config.name ?? t?.attributes.friendly_name ?? r(this.hass, "zone"), it = s?.state ?? f(t, "measurement_quality");
    return l`
      <ha-card>
        <div class="card ${this._config.display_mode === "compact" ? "compact" : ""}">
          <header>
            <div class="hero">
              <ha-icon .icon=${zt(i?.state === "on" ? "safety_lock" : e?.state ?? "unknown")}></ha-icon>
              <div>
                <h2>${Nt}</h2>
                <strong>${i?.state === "on" ? r(this.hass, "locked") : e?.state === "on" ? r(this.hass, "automation_needed") : e?.state === "off" ? r(this.hass, "automation_not_needed") : w(this.hass, e)}</strong>
              </div>
            </div>
          </header>

          ${i?.state === "on" ? l`<div class="warning danger"><ha-icon icon="mdi:lock-alert-outline"></ha-icon><span>${r(this.hass, "safety_lock")}${f(i, "reason") ? `: ${f(i, "reason")}` : ""}</span></div>` : c}
          ${it === "estimated" ? l`<div class="warning"><ha-icon icon="mdi:calculator-variant-outline"></ha-icon><span>${r(this.hass, "warning_estimated")}</span></div>` : it === "unknown" ? l`<div class="warning"><ha-icon icon="mdi:help-circle-outline"></ha-icon><span>${r(this.hass, "warning_unknown")}</span></div>` : c}
          ${o?.state === "off" && f(o, "suspended_until") ? l`<div class="warning"><ha-icon icon="mdi:calendar-clock"></ha-icon><span>${r(this.hass, "automatic_suspended")}: ${f(o, "suspended_until")}</span></div>` : c}
          ${p?.state === "on" ? l`<div class="warning"><ha-icon icon="mdi:archive-outline"></ha-icon><span>${r(this.hass, "archived")}</span></div>` : c}
          ${h && L(h) && Math.abs(Number(h.state)) >= 20 ? l`<div class="warning"><ha-icon icon="mdi:waves-arrow-up"></ha-icon><span>${r(this.hass, "flow_warning")}: ${w(this.hass, h)}</span></div>` : c}

          ${g && _ && L(_) && y !== void 0 ? l`<section><h3>${r(this.hass, "progress")}</h3><strong>${w(this.hass, _)} · ${Math.round(y)}%</strong><progress max="100" .value=${y} aria-label=${r(this.hass, "progress")}></progress></section>` : c}

          <div class="metrics">
            ${this.metric("status", r(this.hass, "status"), a)}
            ${this.metric("balance", r(this.hass, "water_balance"), u(this.hass, this._config.deficit_entity))}
            ${this.metric("balance", r(this.hass, "target"), u(this.hass, this._config.target_entity))}
            ${A.includes("balance") ? this.metric("balance", r(this.hass, "explanation"), u(this.hass, this._config.planning_reason_entity)) : c}
            ${this.metric("next", r(this.hass, "next_window"), u(this.hass, this._config.next_window_entity))}
            ${this.metric("total", r(this.hass, "total"), t)}
            ${this.metric("recent", r(this.hass, "last_delivered"), u(this.hass, this._config.last_delivered_entity))}
            ${this.metric("recent", r(this.hass, "last_duration"), u(this.hass, this._config.last_duration_entity))}
            ${this.metric("quality", r(this.hass, "quality"), s)}
            ${this.metric("calculation", r(this.hass, "coverage"), u(this.hass, this._config.coverage_entity))}
            ${this.metric("calculation", r(this.hass, "explanation"), u(this.hass, this._config.calculation_entity))}
            ${this.metric("flow", r(this.hass, "expected_flow"), u(this.hass, this._config.expected_flow_entity))}
            ${this.metric("flow", r(this.hass, "actual_flow"), u(this.hass, this._config.actual_flow_entity))}
            ${this.metric("flow", r(this.hass, "flow_deviation"), h)}
          </div>
          ${A.includes("history") && Array.isArray(t?.attributes.recent_history) ? l`<section class="details"><h3>${r(this.hass, "history")}</h3>${t.attributes.recent_history.slice(-3).reverse().map((v) => l`<div class="secondary">${String(v.ended_at ?? v.created_at ?? "")} · ${String(v.result ?? v.status ?? "")}</div>`)}</section>` : c}

          <section class="details">
            <h3>${r(this.hass, "manual")}</h3>
            <div class="form-grid">
              <label class="field">
                <span>${r(this.hass, "target")}</span>
                <select .value=${this._targetMode} @change=${(v) => {
      this._targetMode = v.target.value;
    }}>
                  <option value="duration">${r(this.hass, "duration_mode")}</option>
                  <option value="amount">${r(this.hass, "amount_mode")}</option>
                </select>
              </label>
              <label class="field">
                <span>${this._targetMode === "duration" ? r(this.hass, "duration") : r(this.hass, "amount")}</span>
                <input type="number" min="0.001" step=${this._targetMode === "duration" ? "1" : "0.1"} .value=${String(this._targetValue)} @input=${(v) => {
      this._targetValue = Number(v.target.value);
    }} />
                <span>${this._targetMode === "duration" ? r(this.hass, "seconds") : r(this.hass, "liters")}</span>
              </label>
              ${this._targetMode === "amount" ? l`<label class="field"><span>${r(this.hass, "hard_limit")}</span><input type="number" min="0.001" max="14400" step="1" .value=${String(this._hardLimit)} @input=${(v) => {
      this._hardLimit = Number(v.target.value);
    }} /><span>${r(this.hass, "seconds")}</span></label>` : c}
            </div>
          </section>

          ${this._error ? l`<div class="error" role="alert">${this._error}</div>` : c}
          <div class="actions">
            ${$.includes("create") ? l`<button ?disabled=${this._busy || i?.state === "on"} @click=${this.request}><ha-icon icon="mdi:playlist-plus"></ha-icon>${r(this.hass, "create")}</button>` : c}
            ${$.includes("start") ? l`<button class="primary" ?disabled=${this._busy || i?.state === "on"} @click=${this.request}><ha-icon icon="mdi:play"></ha-icon>${r(this.hass, "start")}</button>` : c}
            ${$.includes("pause") ? l`<button ?disabled=${this._busy || !g?.requestId} @click=${() => this.requestAction("pause_request")}><ha-icon icon="mdi:pause"></ha-icon>${r(this.hass, "pause")}</button>` : c}
            ${$.includes("resume") ? l`<button ?disabled=${this._busy || !g?.requestId} @click=${() => this.requestAction("resume_request")}><ha-icon icon="mdi:play-pause"></ha-icon>${r(this.hass, "resume")}</button>` : c}
            ${$.includes("stop") ? l`<button class="danger" ?disabled=${this._busy || !g} @click=${() => this.stop()}><ha-icon icon="mdi:stop-circle-outline"></ha-icon>${r(this.hass, "stop")}</button>` : c}
            ${$.includes("stop_skip") ? l`<button class="danger" ?disabled=${this._busy || !g} @click=${() => this.stop(!0)}><ha-icon icon="mdi:skip-next-circle-outline"></ha-icon>${r(this.hass, "stop_skip")}</button>` : c}
            ${$.includes("suspend") ? l`<button ?disabled=${this._busy || !d || p?.state === "on"} @click=${() => d && this.perform("suspend_automatic", { ...d, until: new Date(Date.now() + 864e5).toISOString() })}><ha-icon icon="mdi:calendar-clock"></ha-icon>${r(this.hass, "suspend_24h")}</button>` : c}
            ${$.includes("resume_auto") ? l`<button ?disabled=${this._busy || !d} @click=${() => d && this.perform("resume_automatic", d)}><ha-icon icon="mdi:calendar-check"></ha-icon>${r(this.hass, "resume_automatic")}</button>` : c}
            ${$.includes("archive") ? l`<button ?disabled=${this._busy || !d || p?.state === "on"} @click=${() => d && this.perform("archive_zone", d, r(this.hass, "confirm_archive"))}><ha-icon icon="mdi:archive-arrow-down-outline"></ha-icon>${r(this.hass, "archive")}</button>` : c}
            ${$.includes("restore") ? l`<button ?disabled=${this._busy || !d || p?.state !== "on"} @click=${() => d && this.perform("restore_zone", d)}><ha-icon icon="mdi:archive-arrow-up-outline"></ha-icon>${r(this.hass, "restore")}</button>` : c}
          </div>
        </div>
      </ha-card>
    `;
  }
};
B.styles = qt, B.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 },
  _targetMode: { state: !0 },
  _targetValue: { state: !0 },
  _hardLimit: { state: !0 },
  _busy: { state: !0 },
  _error: { state: !0 }
};
let J = B;
const _e = [
  ["irrigation-manager-overview-card", K],
  ["irrigation-manager-zone-card", J],
  ["irrigation-manager-overview-card-editor", le],
  ["irrigation-manager-zone-card-editor", de]
];
for (const [n, t] of _e)
  customElements.get(n) || customElements.define(n, t);
window.customCards = window.customCards ?? [];
for (const n of [
  {
    type: "irrigation-manager-overview-card",
    name: "Irrigation Manager Overview",
    description: "Installation status, progress, consumption and safety actions.",
    preview: !0
  },
  {
    type: "irrigation-manager-zone-card",
    name: "Irrigation Manager Zone",
    description: "Water balance, planning details and native zone controls.",
    preview: !0
  }
])
  window.customCards.some((t) => t.type === n.type) || window.customCards.push(n);
