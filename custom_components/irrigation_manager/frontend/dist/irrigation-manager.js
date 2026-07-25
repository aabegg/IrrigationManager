const H = globalThis, tt = H.ShadowRoot && (H.ShadyCSS === void 0 || H.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype, et = /* @__PURE__ */ Symbol(), nt = /* @__PURE__ */ new WeakMap();
let mt = class {
  constructor(t, e, i) {
    if (this._$cssResult$ = !0, i !== et) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
    this.cssText = t, this.t = e;
  }
  get styleSheet() {
    let t = this.o;
    const e = this.t;
    if (tt && t === void 0) {
      const i = e !== void 0 && e.length === 1;
      i && (t = nt.get(e)), t === void 0 && ((this.o = t = new CSSStyleSheet()).replaceSync(this.cssText), i && nt.set(e, t));
    }
    return t;
  }
  toString() {
    return this.cssText;
  }
};
const kt = (r) => new mt(typeof r == "string" ? r : r + "", void 0, et), ft = (r, ...t) => {
  const e = r.length === 1 ? r[0] : t.reduce((i, s, n) => i + ((a) => {
    if (a._$cssResult$ === !0) return a.cssText;
    if (typeof a == "number") return a;
    throw Error("Value passed to 'css' function must be a 'css' function result: " + a + ". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.");
  })(s) + r[n + 1], r[0]);
  return new mt(e, r, et);
}, zt = (r, t) => {
  if (tt) r.adoptedStyleSheets = t.map((e) => e instanceof CSSStyleSheet ? e : e.styleSheet);
  else for (const e of t) {
    const i = document.createElement("style"), s = H.litNonce;
    s !== void 0 && i.setAttribute("nonce", s), i.textContent = e.cssText, r.appendChild(i);
  }
}, ot = tt ? (r) => r : (r) => r instanceof CSSStyleSheet ? ((t) => {
  let e = "";
  for (const i of t.cssRules) e += i.cssText;
  return kt(e);
})(r) : r;
const { is: Ct, defineProperty: Ot, getOwnPropertyDescriptor: Mt, getOwnPropertyNames: Pt, getOwnPropertySymbols: Nt, getPrototypeOf: Tt } = Object, q = globalThis, at = q.trustedTypes, Rt = at ? at.emptyScript : "", Ut = q.reactiveElementPolyfillSupport, k = (r, t) => r, Q = { toAttribute(r, t) {
  switch (t) {
    case Boolean:
      r = r ? Rt : null;
      break;
    case Object:
    case Array:
      r = r == null ? r : JSON.stringify(r);
  }
  return r;
}, fromAttribute(r, t) {
  let e = r;
  switch (t) {
    case Boolean:
      e = r !== null;
      break;
    case Number:
      e = r === null ? null : Number(r);
      break;
    case Object:
    case Array:
      try {
        e = JSON.parse(r);
      } catch {
        e = null;
      }
  }
  return e;
} }, yt = (r, t) => !Ct(r, t), lt = { attribute: !0, type: String, converter: Q, reflect: !1, useDefault: !1, hasChanged: yt };
Symbol.metadata ??= /* @__PURE__ */ Symbol("metadata"), q.litPropertyMetadata ??= /* @__PURE__ */ new WeakMap();
let w = class extends HTMLElement {
  static addInitializer(t) {
    this._$Ei(), (this.l ??= []).push(t);
  }
  static get observedAttributes() {
    return this.finalize(), this._$Eh && [...this._$Eh.keys()];
  }
  static createProperty(t, e = lt) {
    if (e.state && (e.attribute = !1), this._$Ei(), this.prototype.hasOwnProperty(t) && ((e = Object.create(e)).wrapped = !0), this.elementProperties.set(t, e), !e.noAccessor) {
      const i = /* @__PURE__ */ Symbol(), s = this.getPropertyDescriptor(t, i, e);
      s !== void 0 && Ot(this.prototype, t, s);
    }
  }
  static getPropertyDescriptor(t, e, i) {
    const { get: s, set: n } = Mt(this.prototype, t) ?? { get() {
      return this[e];
    }, set(a) {
      this[e] = a;
    } };
    return { get: s, set(a) {
      const c = s?.call(this);
      n?.call(this, a), this.requestUpdate(t, c, i);
    }, configurable: !0, enumerable: !0 };
  }
  static getPropertyOptions(t) {
    return this.elementProperties.get(t) ?? lt;
  }
  static _$Ei() {
    if (this.hasOwnProperty(k("elementProperties"))) return;
    const t = Tt(this);
    t.finalize(), t.l !== void 0 && (this.l = [...t.l]), this.elementProperties = new Map(t.elementProperties);
  }
  static finalize() {
    if (this.hasOwnProperty(k("finalized"))) return;
    if (this.finalized = !0, this._$Ei(), this.hasOwnProperty(k("properties"))) {
      const e = this.properties, i = [...Pt(e), ...Nt(e)];
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
      for (const s of i) e.unshift(ot(s));
    } else t !== void 0 && e.push(ot(t));
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
    return zt(t, this.constructor.elementStyles), t;
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
      const n = (i.converter?.toAttribute !== void 0 ? i.converter : Q).toAttribute(e, i.type);
      this._$Em = t, n == null ? this.removeAttribute(s) : this.setAttribute(s, n), this._$Em = null;
    }
  }
  _$AK(t, e) {
    const i = this.constructor, s = i._$Eh.get(t);
    if (s !== void 0 && this._$Em !== s) {
      const n = i.getPropertyOptions(s), a = typeof n.converter == "function" ? { fromAttribute: n.converter } : n.converter?.fromAttribute !== void 0 ? n.converter : Q;
      this._$Em = s;
      const c = a.fromAttribute(e, n.type);
      this[s] = c ?? this._$Ej?.get(s) ?? c, this._$Em = null;
    }
  }
  requestUpdate(t, e, i, s = !1, n) {
    if (t !== void 0) {
      const a = this.constructor;
      if (s === !1 && (n = this[t]), i ??= a.getPropertyOptions(t), !((i.hasChanged ?? yt)(n, e) || i.useDefault && i.reflect && n === this._$Ej?.get(t) && !this.hasAttribute(a._$Eu(t, i)))) return;
      this.C(t, e, i);
    }
    this.isUpdatePending === !1 && (this._$ES = this._$EP());
  }
  C(t, e, { useDefault: i, reflect: s, wrapped: n }, a) {
    i && !(this._$Ej ??= /* @__PURE__ */ new Map()).has(t) && (this._$Ej.set(t, a ?? e ?? this[t]), n !== !0 || a !== void 0) || (this._$AL.has(t) || (this.hasUpdated || i || (e = void 0), this._$AL.set(t, e)), s === !0 && this._$Em !== t && (this._$Eq ??= /* @__PURE__ */ new Set()).add(t));
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
        for (const [s, n] of this._$Ep) this[s] = n;
        this._$Ep = void 0;
      }
      const i = this.constructor.elementProperties;
      if (i.size > 0) for (const [s, n] of i) {
        const { wrapped: a } = n, c = this[s];
        a !== !0 || this._$AL.has(s) || c === void 0 || this.C(s, void 0, n, c);
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
w.elementStyles = [], w.shadowRootOptions = { mode: "open" }, w[k("elementProperties")] = /* @__PURE__ */ new Map(), w[k("finalized")] = /* @__PURE__ */ new Map(), Ut?.({ ReactiveElement: w }), (q.reactiveElementVersions ??= []).push("2.1.2");
const it = globalThis, ht = (r) => r, L = it.trustedTypes, ct = L ? L.createPolicy("lit-html", { createHTML: (r) => r }) : void 0, $t = "$lit$", y = `lit$${Math.random().toFixed(9).slice(2)}$`, vt = "?" + y, Ht = `<${vt}>`, x = document, M = () => x.createComment(""), P = (r) => r === null || typeof r != "object" && typeof r != "function", st = Array.isArray, Lt = (r) => st(r) || typeof r?.[Symbol.iterator] == "function", Z = `[\x20\t\n\f\r]`, E = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g, dt = /-->/g, ut = />/g, $ = RegExp(`>|${Z}(?:([^\\s"'>=/]+)(${Z}*=${Z}*(?:[^\x20\t\n\f\r"'\`<>=]|("|')|))|$)`, "g"), pt = /'/g, _t = /"/g, bt = /^(?:script|style|textarea|title)$/i, It = (r) => (t, ...e) => ({ _$litType$: r, strings: t, values: e }), u = It(1), A = /* @__PURE__ */ Symbol.for("lit-noChange"), d = /* @__PURE__ */ Symbol.for("lit-nothing"), gt = /* @__PURE__ */ new WeakMap(), v = x.createTreeWalker(x, 129);
function xt(r, t) {
  if (!st(r) || !r.hasOwnProperty("raw")) throw Error("invalid template strings array");
  return ct !== void 0 ? ct.createHTML(t) : t;
}
const Dt = (r, t) => {
  const e = r.length - 1, i = [];
  let s, n = t === 2 ? "<svg>" : t === 3 ? "<math>" : "", a = E;
  for (let c = 0; c < e; c++) {
    const h = r[c];
    let l, g, p = -1, m = 0;
    for (; m < h.length && (a.lastIndex = m, g = a.exec(h), g !== null); ) m = a.lastIndex, a === E ? g[1] === "!--" ? a = dt : g[1] !== void 0 ? a = ut : g[2] !== void 0 ? (bt.test(g[2]) && (s = RegExp("</" + g[2], "g")), a = $) : g[3] !== void 0 && (a = $) : a === $ ? g[0] === ">" ? (a = s ?? E, p = -1) : g[1] === void 0 ? p = -2 : (p = a.lastIndex - g[2].length, l = g[1], a = g[3] === void 0 ? $ : g[3] === '"' ? _t : pt) : a === _t || a === pt ? a = $ : a === dt || a === ut ? a = E : (a = $, s = void 0);
    const f = a === $ && r[c + 1].startsWith("/>") ? " " : "";
    n += a === E ? h + Ht : p >= 0 ? (i.push(l), h.slice(0, p) + $t + h.slice(p) + y + f) : h + y + (p === -2 ? c : f);
  }
  return [xt(r, n + (r[e] || "<?>") + (t === 2 ? "</svg>" : t === 3 ? "</math>" : "")), i];
};
class N {
  constructor({ strings: t, _$litType$: e }, i) {
    let s;
    this.parts = [];
    let n = 0, a = 0;
    const c = t.length - 1, h = this.parts, [l, g] = Dt(t, e);
    if (this.el = N.createElement(l, i), v.currentNode = this.el.content, e === 2 || e === 3) {
      const p = this.el.content.firstChild;
      p.replaceWith(...p.childNodes);
    }
    for (; (s = v.nextNode()) !== null && h.length < c; ) {
      if (s.nodeType === 1) {
        if (s.hasAttributes()) for (const p of s.getAttributeNames()) if (p.endsWith($t)) {
          const m = g[a++], f = s.getAttribute(p).split(y), R = /([.?@])?(.*)/.exec(m);
          h.push({ type: 1, index: n, name: R[2], strings: f, ctor: R[1] === "." ? jt : R[1] === "?" ? Bt : R[1] === "@" ? Wt : F }), s.removeAttribute(p);
        } else p.startsWith(y) && (h.push({ type: 6, index: n }), s.removeAttribute(p));
        if (bt.test(s.tagName)) {
          const p = s.textContent.split(y), m = p.length - 1;
          if (m > 0) {
            s.textContent = L ? L.emptyScript : "";
            for (let f = 0; f < m; f++) s.append(p[f], M()), v.nextNode(), h.push({ type: 2, index: ++n });
            s.append(p[m], M());
          }
        }
      } else if (s.nodeType === 8) if (s.data === vt) h.push({ type: 2, index: n });
      else {
        let p = -1;
        for (; (p = s.data.indexOf(y, p + 1)) !== -1; ) h.push({ type: 7, index: n }), p += y.length - 1;
      }
      n++;
    }
  }
  static createElement(t, e) {
    const i = x.createElement("template");
    return i.innerHTML = t, i;
  }
}
function S(r, t, e = r, i) {
  if (t === A) return t;
  let s = i !== void 0 ? e._$Co?.[i] : e._$Cl;
  const n = P(t) ? void 0 : t._$litDirective$;
  return s?.constructor !== n && (s?._$AO?.(!1), n === void 0 ? s = void 0 : (s = new n(r), s._$AT(r, e, i)), i !== void 0 ? (e._$Co ??= [])[i] = s : e._$Cl = s), s !== void 0 && (t = S(r, s._$AS(r, t.values), s, i)), t;
}
class Vt {
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
    const { el: { content: e }, parts: i } = this._$AD, s = (t?.creationScope ?? x).importNode(e, !0);
    v.currentNode = s;
    let n = v.nextNode(), a = 0, c = 0, h = i[0];
    for (; h !== void 0; ) {
      if (a === h.index) {
        let l;
        h.type === 2 ? l = new T(n, n.nextSibling, this, t) : h.type === 1 ? l = new h.ctor(n, h.name, h.strings, this, t) : h.type === 6 && (l = new qt(n, this, t)), this._$AV.push(l), h = i[++c];
      }
      a !== h?.index && (n = v.nextNode(), a++);
    }
    return v.currentNode = x, s;
  }
  p(t) {
    let e = 0;
    for (const i of this._$AV) i !== void 0 && (i.strings !== void 0 ? (i._$AI(t, i, e), e += i.strings.length - 2) : i._$AI(t[e])), e++;
  }
}
class T {
  get _$AU() {
    return this._$AM?._$AU ?? this._$Cv;
  }
  constructor(t, e, i, s) {
    this.type = 2, this._$AH = d, this._$AN = void 0, this._$AA = t, this._$AB = e, this._$AM = i, this.options = s, this._$Cv = s?.isConnected ?? !0;
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
    t = S(this, t, e), P(t) ? t === d || t == null || t === "" ? (this._$AH !== d && this._$AR(), this._$AH = d) : t !== this._$AH && t !== A && this._(t) : t._$litType$ !== void 0 ? this.$(t) : t.nodeType !== void 0 ? this.T(t) : Lt(t) ? this.k(t) : this._(t);
  }
  O(t) {
    return this._$AA.parentNode.insertBefore(t, this._$AB);
  }
  T(t) {
    this._$AH !== t && (this._$AR(), this._$AH = this.O(t));
  }
  _(t) {
    this._$AH !== d && P(this._$AH) ? this._$AA.nextSibling.data = t : this.T(x.createTextNode(t)), this._$AH = t;
  }
  $(t) {
    const { values: e, _$litType$: i } = t, s = typeof i == "number" ? this._$AC(t) : (i.el === void 0 && (i.el = N.createElement(xt(i.h, i.h[0]), this.options)), i);
    if (this._$AH?._$AD === s) this._$AH.p(e);
    else {
      const n = new Vt(s, this), a = n.u(this.options);
      n.p(e), this.T(a), this._$AH = n;
    }
  }
  _$AC(t) {
    let e = gt.get(t.strings);
    return e === void 0 && gt.set(t.strings, e = new N(t)), e;
  }
  k(t) {
    st(this._$AH) || (this._$AH = [], this._$AR());
    const e = this._$AH;
    let i, s = 0;
    for (const n of t) s === e.length ? e.push(i = new T(this.O(M()), this.O(M()), this, this.options)) : i = e[s], i._$AI(n), s++;
    s < e.length && (this._$AR(i && i._$AB.nextSibling, s), e.length = s);
  }
  _$AR(t = this._$AA.nextSibling, e) {
    for (this._$AP?.(!1, !0, e); t !== this._$AB; ) {
      const i = ht(t).nextSibling;
      ht(t).remove(), t = i;
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
  constructor(t, e, i, s, n) {
    this.type = 1, this._$AH = d, this._$AN = void 0, this.element = t, this.name = e, this._$AM = s, this.options = n, i.length > 2 || i[0] !== "" || i[1] !== "" ? (this._$AH = Array(i.length - 1).fill(new String()), this.strings = i) : this._$AH = d;
  }
  _$AI(t, e = this, i, s) {
    const n = this.strings;
    let a = !1;
    if (n === void 0) t = S(this, t, e, 0), a = !P(t) || t !== this._$AH && t !== A, a && (this._$AH = t);
    else {
      const c = t;
      let h, l;
      for (t = n[0], h = 0; h < n.length - 1; h++) l = S(this, c[i + h], e, h), l === A && (l = this._$AH[h]), a ||= !P(l) || l !== this._$AH[h], l === d ? t = d : t !== d && (t += (l ?? "") + n[h + 1]), this._$AH[h] = l;
    }
    a && !s && this.j(t);
  }
  j(t) {
    t === d ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, t ?? "");
  }
}
class jt extends F {
  constructor() {
    super(...arguments), this.type = 3;
  }
  j(t) {
    this.element[this.name] = t === d ? void 0 : t;
  }
}
class Bt extends F {
  constructor() {
    super(...arguments), this.type = 4;
  }
  j(t) {
    this.element.toggleAttribute(this.name, !!t && t !== d);
  }
}
class Wt extends F {
  constructor(t, e, i, s, n) {
    super(t, e, i, s, n), this.type = 5;
  }
  _$AI(t, e = this) {
    if ((t = S(this, t, e, 0) ?? d) === A) return;
    const i = this._$AH, s = t === d && i !== d || t.capture !== i.capture || t.once !== i.once || t.passive !== i.passive, n = t !== d && (i === d || s);
    s && this.element.removeEventListener(this.name, this, i), n && this.element.addEventListener(this.name, this, t), this._$AH = t;
  }
  handleEvent(t) {
    typeof this._$AH == "function" ? this._$AH.call(this.options?.host ?? this.element, t) : this._$AH.handleEvent(t);
  }
}
class qt {
  constructor(t, e, i) {
    this.element = t, this.type = 6, this._$AN = void 0, this._$AM = e, this.options = i;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  _$AI(t) {
    S(this, t);
  }
}
const Ft = it.litHtmlPolyfillSupport;
Ft?.(N, T), (it.litHtmlVersions ??= []).push("3.3.3");
const Zt = (r, t, e) => {
  const i = e?.renderBefore ?? t;
  let s = i._$litPart$;
  if (s === void 0) {
    const n = e?.renderBefore ?? null;
    i._$litPart$ = s = new T(t.insertBefore(M(), n), n, void 0, e ?? {});
  }
  return s._$AI(r), s;
};
const rt = globalThis;
class b extends w {
  constructor() {
    super(...arguments), this.renderOptions = { host: this }, this._$Do = void 0;
  }
  createRenderRoot() {
    const t = super.createRenderRoot();
    return this.renderOptions.renderBefore ??= t.firstChild, t;
  }
  update(t) {
    const e = this.render();
    this.hasUpdated || (this.renderOptions.isConnected = this.isConnected), super.update(t), this._$Do = Zt(e, this.renderRoot, this.renderOptions);
  }
  connectedCallback() {
    super.connectedCallback(), this._$Do?.setConnected(!0);
  }
  disconnectedCallback() {
    super.disconnectedCallback(), this._$Do?.setConnected(!1);
  }
  render() {
    return A;
  }
}
b._$litElement$ = !0, b.finalized = !0, rt.litElementHydrateSupport?.({ LitElement: b });
const Kt = rt.litElementPolyfillSupport;
Kt?.({ LitElement: b });
(rt.litElementVersions ??= []).push("4.2.2");
const I = "irrigation_manager", Gt = /* @__PURE__ */ new Set(["unknown", "unavailable"]), Jt = {
  status: "status_entity",
  pending: "pending_entity",
  next: "next_entity",
  next_start: "next_start_entity",
  today_consumption: "today_consumption_entity",
  month_consumption: "month_consumption_entity",
  runtime_today: "runtime_today_entity",
  runtime_month: "runtime_month_entity",
  physical_meter: "physical_meter_entity"
}, Qt = {
  anchor: "zone_entity",
  zone: "zone_entity",
  status: "status_entity",
  water_today: "water_today_entity",
  water_month: "water_month_entity",
  runtime_today: "runtime_today_entity",
  runtime_month: "runtime_month_entity",
  next_irrigation: "next_irrigation_entity"
};
function D(r, t) {
  const e = r?.attributes[t];
  return !e || typeof e != "object" || Array.isArray(e) ? {} : Object.fromEntries(
    Object.entries(e).filter(
      (i) => typeof i[1] == "string" && i[1].includes(".")
    )
  );
}
function wt(r, t, e) {
  const i = { ...r };
  for (const [s, n] of Object.entries(e)) {
    const c = r[n] || t[s];
    c && Object.assign(i, { [n]: c });
  }
  return i;
}
function K(r, t) {
  const e = t.entity ? r.states[t.entity] : void 0, i = { ...t };
  return wt(i, D(e, "card_entities"), Jt);
}
function G(r, t) {
  const e = t.entity ? r.states[t.entity] : void 0, i = { ...t }, s = wt(i, D(e, "card_entities"), Qt);
  return !s.zone_entity && e && (s.zone_entity = e.entity_id), !s.status_entity && e && (s.status_entity = e.entity_id), s;
}
function Xt(r, t) {
  if (typeof r.attributes.config_entry_id != "string") return !1;
  if (t === "installation")
    return typeof r.attributes.zone_subentry_id == "string" ? !1 : D(r, "card_entities").status === r.entity_id;
  if (typeof r.attributes.zone_subentry_id != "string") return !1;
  const s = D(r, "card_entities");
  return s.anchor ? s.anchor === r.entity_id : s.zone === r.entity_id;
}
function Yt(r, t) {
  return Object.values(r.states).filter((e) => Xt(e, t)).map((e) => ({
    value: e.entity_id,
    label: typeof e.attributes.card_name == "string" && e.attributes.card_name || e.attributes.friendly_name || e.entity_id
  })).sort((e, i) => e.label.localeCompare(i.label, r.language));
}
function _(r, t) {
  return t ? r.states[t] : void 0;
}
function te(r) {
  return !!(r && !Gt.has(r.state));
}
function z(r, t) {
  const e = r?.attributes[t];
  return typeof e == "string" && e ? e : void 0;
}
function U(r, t) {
  const e = r?.attributes[t];
  return typeof e == "number" && Number.isFinite(e) ? e : void 0;
}
function At(r) {
  return {
    idle: "mdi:water-check-outline",
    watering: "mdi:sprinkler-variant",
    error: "mdi:alert-circle-outline",
    safety_lock: "mdi:lock-alert-outline",
    emergency_stop: "mdi:alert-octagon",
    disabled: "mdi:water-off-outline",
    automatic_disabled: "mdi:calendar-remove-outline",
    installation_disabled: "mdi:power-plug-off-outline",
    needs_reconfiguration: "mdi:cog-alert-outline",
    unavailable: "mdi:cloud-alert-outline",
    unknown: "mdi:help-circle-outline",
    on: "mdi:check-circle-outline",
    off: "mdi:minus-circle-outline"
  }[r] ?? "mdi:information-outline";
}
function ee(r, t) {
  r.dispatchEvent(
    new CustomEvent("config-changed", {
      detail: { config: t },
      bubbles: !0,
      composed: !0
    })
  );
}
const St = {
  en: {
    overview: "Irrigation overview",
    zone: "Irrigation zone",
    unavailable: "Unavailable",
    unknown: "Unknown",
    missing: "Entity not found",
    idle: "Idle",
    watering: "Watering",
    error: "Error",
    safety_lock: "Safety lock",
    emergency_stop: "Emergency stop",
    needs_reconfiguration: "Reconfiguration required",
    disabled: "Disabled",
    automatic_disabled: "Active, automatic irrigation disabled",
    installation_disabled: "Installation disabled",
    on: "On",
    off: "Off",
    pending: "Open requests",
    next: "Next irrigation",
    emergency: "Emergency stop",
    action_failed: "Action failed",
    configuration_error: "The selected entity does not expose the identifiers required by this action.",
    locked: "Locked",
    unlocked: "Ready",
    target: "Target",
    amount: "Amount",
    duration: "Duration",
    hard_limit: "Maximum duration",
    liters: "L",
    seconds: "s",
    start: "Start now",
    invalid_target: "Enter a value greater than zero.",
    hard_limit_required: "A maximum duration is required for amount control.",
    status: "Status",
    amount_mode: "Amount controlled",
    duration_mode: "Time controlled",
    installation: "Irrigation installation",
    physical_meter: "Physical meter",
    next_zone: "Next zone",
    expected_start: "Expected start",
    runtime_today: "Runtime today",
    runtime_month: "Runtime this month",
    water_today: "Measured water today",
    water_month: "Measured water this month",
    irrigation_orders: "Irrigation orders",
    no_open_orders: "No open irrigation orders",
    close: "Close",
    loading: "Loading...",
    manual_water: "Water manually",
    show_history: "Show history",
    active_execution_choice: "Another irrigation execution is active",
    stop_active_start_now: "Stop active execution and start now",
    finish_then_priority: "Finish active execution and run next",
    irrigation_history: "Irrigation history",
    source: "Source",
    result: "Result",
    all: "All",
    manual: "Manual",
    automatic: "Automatic",
    completed: "Completed",
    failed: "Failed",
    cancelled: "Cancelled",
    previous: "Previous",
    next_page: "Next"
  },
  de: {
    overview: "Bewässerungsübersicht",
    zone: "Bewässerungszone",
    unavailable: "Nicht verfügbar",
    unknown: "Unbekannt",
    missing: "Entity nicht gefunden",
    idle: "Bereit",
    watering: "Bewässerung läuft",
    error: "Fehler",
    safety_lock: "Sicherheitssperre",
    emergency_stop: "Not-Aus aktiv",
    needs_reconfiguration: "Neukonfiguration erforderlich",
    disabled: "Deaktiviert",
    automatic_disabled: "Aktiv, Automatik deaktiviert",
    installation_disabled: "Anlage deaktiviert",
    on: "Ein",
    off: "Aus",
    pending: "Offene Aufträge",
    next: "Nächste Bewässerung",
    emergency: "Not-Aus",
    action_failed: "Aktion fehlgeschlagen",
    configuration_error: "Die gewählte Entity stellt die für diese Aktion benötigten Kennungen nicht bereit.",
    locked: "Gesperrt",
    unlocked: "Bereit",
    target: "Bewässerungsziel",
    amount: "Menge",
    duration: "Dauer",
    hard_limit: "Maximale Dauer",
    liters: "L",
    seconds: "s",
    start: "Sofort starten",
    invalid_target: "Einen Wert größer als null eingeben.",
    hard_limit_required: "Für die Mengensteuerung ist eine maximale Dauer erforderlich.",
    status: "Status",
    amount_mode: "Mengengesteuert",
    duration_mode: "Zeitgesteuert",
    installation: "Bewässerungsanlage",
    physical_meter: "Physischer Zählerstand",
    next_zone: "Nächste Zone",
    expected_start: "Erwarteter Start",
    runtime_today: "Laufzeit heute",
    runtime_month: "Laufzeit diesen Monat",
    water_today: "Gemessenes Wasser heute",
    water_month: "Gemessenes Wasser diesen Monat",
    irrigation_orders: "Bewässerungsaufträge",
    no_open_orders: "Keine offenen Bewässerungsaufträge",
    close: "Schließen",
    loading: "Wird geladen...",
    manual_water: "Manuell bewässern",
    show_history: "Verlauf anzeigen",
    active_execution_choice: "Ein anderer Bewässerungsvorgang ist aktiv",
    stop_active_start_now: "Aktiven Vorgang beenden und sofort starten",
    finish_then_priority: "Aktiven Vorgang abschließen und danach ausführen",
    irrigation_history: "Bewässerungsverlauf",
    source: "Quelle",
    result: "Ergebnis",
    all: "Alle",
    manual: "Manuell",
    automatic: "Automatisch",
    completed: "Abgeschlossen",
    failed: "Fehlgeschlagen",
    cancelled: "Abgebrochen",
    previous: "Zurück",
    next_page: "Weiter"
  }
};
function o(r, t) {
  const e = r.language?.toLowerCase().startsWith("de") ? "de" : "en";
  return St[e][t];
}
function C(r, t) {
  return t in St.en ? o(r, t) : t.replaceAll("_", " ");
}
function O(r, t) {
  if (!t) return o(r, "missing");
  if (t.state === "unavailable") return o(r, "unavailable");
  if (t.state === "unknown" || t.state === "") return o(r, "unknown");
  if (r.formatEntityState) return r.formatEntityState(t);
  const e = t.attributes.unit_of_measurement;
  return `${C(r, t.state)}${e ? ` ${e}` : ""}`;
}
const Et = ft`
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
  .metric { padding: 10px 12px; border: 1px solid var(--divider-color); border-radius: var(--ha-card-border-radius, 12px); min-width: 0; text-align: left; }
  .metric span { display: block; color: var(--secondary-text-color); font-size: 0.78rem; margin-bottom: 3px; }
  .warning { display: flex; align-items: flex-start; gap: 8px; padding: 10px 12px; border-left: 4px solid var(--warning-color, var(--primary-color)); background: var(--secondary-background-color); border-radius: 4px; }
  .warning.danger { border-left-color: var(--error-color); }
  progress { width: 100%; height: 8px; accent-color: var(--primary-color); }
  .actions { display: flex; flex-wrap: wrap; gap: 8px; }
  button { min-height: 40px; padding: 0 14px; border: 1px solid var(--divider-color); border-radius: 10px; background: var(--card-background-color); color: var(--primary-text-color); font: inherit; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: 7px; }
  button.primary { background: var(--primary-color); border-color: var(--primary-color); color: var(--text-primary-color, white); }
  button.danger { border-color: var(--error-color); color: var(--error-color); }
  button.emergency { background: var(--error-color); border-color: var(--error-color); color: white; font-weight: 700; }
  button.metric-button { display: block; min-height: auto; cursor: pointer; }
  button:disabled { opacity: 0.45; cursor: not-allowed; }
  button:focus-visible, input:focus-visible, select:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
  .form-grid { display: grid; grid-template-columns: minmax(130px, 1fr) minmax(110px, 1fr); gap: 10px; align-items: end; }
  label.field { display: grid; gap: 5px; color: var(--secondary-text-color); font-size: 0.8rem; }
  input, select { box-sizing: border-box; width: 100%; min-height: 40px; padding: 8px 10px; color: var(--primary-text-color); background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 8px; font: inherit; }
  .error { color: var(--error-color); font-size: 0.875rem; }
  .compact .details { display: none; }
  dialog { box-sizing: border-box; width: min(680px, calc(100% - 24px)); max-height: min(80vh, 720px); overflow: auto; border: 0; border-radius: var(--ha-card-border-radius, 12px); padding: 18px; color: var(--primary-text-color); background: var(--card-background-color); box-shadow: var(--ha-card-box-shadow, 0 4px 20px rgb(0 0 0 / 0.28)); }
  dialog[open] { position: fixed; inset: 50% auto auto 50%; transform: translate(-50%, -50%); z-index: 10; }
  .dialog-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
  .icon-button { min-width: 40px; padding: 0; font-size: 1.5rem; }
  .table { display: grid; gap: 8px; }
  .table-row { display: grid; grid-template-columns: minmax(100px, 1.2fr) repeat(4, minmax(90px, 1fr)); gap: 8px; padding: 10px 0; border-bottom: 1px solid var(--divider-color); align-items: center; }
  .filters { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-bottom: 14px; }
  .history-list { display: grid; gap: 8px; }
  .history-list article { display: grid; gap: 3px; padding: 10px 0; border-bottom: 1px solid var(--divider-color); }
  .history-list article span { color: var(--secondary-text-color); font-size: 0.82rem; }
  .dialog-actions { margin-top: 16px; justify-content: flex-end; }
  @container (max-width: 520px) { .table-row { grid-template-columns: 1fr 1fr; } }
  :host { container-type: inline-size; }
  @media (max-width: 480px) {
    .card { padding: 14px; }
    .form-grid { grid-template-columns: 1fr; }
    .actions button { flex: 1 1 calc(50% - 8px); }
  }
`, ie = ft`
  :host { display: block; }
  .editor { display: grid; gap: 18px; padding: 8px 0; }
  section { display: grid; gap: 10px; }
  h3 { margin: 0; font-size: 1rem; }
  label.selector { display: grid; gap: 5px; color: var(--secondary-text-color); }
  label.selector small { line-height: 1.35; }
  .checks { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 6px 12px; }
  .check { display: flex; align-items: center; gap: 8px; min-height: 34px; }
  input[type="checkbox"] { width: 18px; height: 18px; accent-color: var(--primary-color); }
  select { min-height: 40px; padding: 8px; color: var(--primary-text-color); background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 8px; }
`, j = class j extends b {
  setConfig(t) {
    this._config = { ...t };
  }
  updateValue(t, e) {
    const i = { ...this._config, [t]: e || void 0 };
    e || delete i[t], this._config = i, ee(this, i);
  }
  anchorSelector(t) {
    const e = Yt(this.hass, t);
    return u`
      <label class="selector">
        <span>${o(this.hass, t)}</span>
        <ha-selector
          data-testid="anchor-selector"
          .hass=${this.hass}
          .value=${this._config.entity ?? ""}
          .selector=${{ entity: { include_entities: e.map((i) => i.value) } }}
          @value-changed=${(i) => this.updateValue("entity", i.detail.value)}
        ></ha-selector>
      </label>
    `;
  }
};
j.styles = ie, j.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 }
};
let V = j;
class se extends V {
  render() {
    return !this.hass || !this._config ? d : u`
      <div class="editor">
        <section>${this.anchorSelector("installation")}</section>
      </div>
    `;
  }
}
class re extends V {
  render() {
    return !this.hass || !this._config ? d : u`
      <div class="editor">
        <section>${this.anchorSelector("zone")}</section>
      </div>
    `;
  }
}
const B = class B extends b {
  constructor() {
    super(...arguments), this._busy = !1, this._ordersOpen = !1, this._orders = [];
  }
  static getConfigElement() {
    return document.createElement("irrigation-manager-overview-card-editor");
  }
  static getStubConfig() {
    return {
      type: "custom:irrigation-manager-overview-card",
      entity: ""
    };
  }
  setConfig(t) {
    this._config = { ...t };
  }
  getCardSize() {
    return 5;
  }
  metric(t, e) {
    return u`<div class="metric"><span>${t}</span><strong>${O(this.hass, e)}</strong></div>`;
  }
  async call(t, e, i = {}) {
    if (e && !window.confirm(e)) return;
    const s = K(this.hass, this._config), n = _(this.hass, s.status_entity), a = z(n, "config_entry_id");
    if (!a) {
      this._error = o(this.hass, "configuration_error");
      return;
    }
    this._busy = !0, this._error = void 0;
    try {
      await this.hass.callService(I, t, { config_entry_id: a, ...i });
    } catch (c) {
      this._error = `${o(this.hass, "action_failed")}: ${c instanceof Error ? c.message : String(c)}`;
    } finally {
      this._busy = !1;
    }
  }
  async openOrders() {
    const t = K(this.hass, this._config), e = z(_(this.hass, t.status_entity), "config_entry_id");
    if (e) {
      this._ordersOpen = !0, this._busy = !0, this._error = void 0;
      try {
        const i = await this.hass.callService(
          I,
          "list_card_orders",
          { config_entry_id: e },
          void 0,
          !0
        );
        this._orders = i.orders ?? [];
      } catch (i) {
        this._error = `${o(this.hass, "action_failed")}: ${i instanceof Error ? i.message : String(i)}`;
      } finally {
        this._busy = !1;
      }
    }
  }
  target(t) {
    return `${String(t.target_value)} ${t.target_type === "volume" ? o(this.hass, "liters") : o(this.hass, "seconds")}`;
  }
  render() {
    if (!this.hass || !this._config) return d;
    const t = K(this.hass, this._config);
    if (!t.status_entity || !_(this.hass, t.status_entity))
      return u`<ha-card><div class="card"><div class="warning"><ha-icon icon="mdi:water-alert"></ha-icon><span>${o(this.hass, "missing")}</span></div></div></ha-card>`;
    const e = _(this.hass, t.status_entity), i = z(e, "config_entry_id"), s = e?.state ?? "unavailable", n = e?.attributes.volume_control_available === !0, a = typeof e?.attributes.card_name == "string" ? e.attributes.card_name : e?.attributes.friendly_name ?? o(this.hass, "overview");
    return u`
      <ha-card>
        <div class="card">
          <header>
            <div class="hero">
              <ha-icon .icon=${At(s)}></ha-icon>
              <div>
                <h2>${a}</h2>
                <strong>${te(e) ? C(this.hass, e.state) : O(this.hass, e)}</strong>
              </div>
            </div>
          </header>

          <div class="metrics">
            <button class="metric metric-button" data-testid="open-orders" ?disabled=${this._busy || !i} @click=${this.openOrders}><span>${o(this.hass, "pending")}</span><strong>${O(this.hass, _(this.hass, t.pending_entity))}</strong></button>
            ${this.metric(o(this.hass, "next_zone"), _(this.hass, t.next_entity))}
            ${this.metric(o(this.hass, "expected_start"), _(this.hass, t.next_start_entity))}
            ${this.metric(o(this.hass, n ? "water_today" : "runtime_today"), _(this.hass, n ? t.today_consumption_entity : t.runtime_today_entity))}
            ${this.metric(o(this.hass, n ? "water_month" : "runtime_month"), _(this.hass, n ? t.month_consumption_entity : t.runtime_month_entity))}
            ${n ? this.metric(o(this.hass, "physical_meter"), _(this.hass, t.physical_meter_entity)) : d}
          </div>

          ${this._error ? u`<div class="error" role="alert">${this._error}</div>` : d}
          <div class="actions">
            <button class="danger emergency" data-testid="emergency-stop" ?disabled=${this._busy || !i} @click=${() => this.call("emergency_stop")}><ha-icon icon="mdi:alert-octagon-outline"></ha-icon>${o(this.hass, "emergency")}</button>
          </div>
          ${this._ordersOpen ? u`
            <dialog open aria-labelledby="orders-title">
              <div class="dialog-header"><h2 id="orders-title">${o(this.hass, "irrigation_orders")}</h2><button class="icon-button" aria-label=${o(this.hass, "close")} @click=${() => {
      this._ordersOpen = !1;
    }}>×</button></div>
              ${this._busy ? u`<p aria-live="polite">${o(this.hass, "loading")}</p>` : this._orders.length === 0 ? u`<p>${o(this.hass, "no_open_orders")}</p>` : u`
                <div class="table" role="table">
                  ${this._orders.map((c) => u`<div class="table-row" role="row"><strong>${String(c.zone)}</strong><span>${C(this.hass, String(c.source))}</span><span>${this.target(c)}</span><span>${String(c.expected_start)}</span><span>${C(this.hass, String(c.status))}</span></div>`)}
                </div>`}
            </dialog>` : d}
        </div>
      </ha-card>
    `;
  }
};
B.styles = Et, B.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 },
  _busy: { state: !0 },
  _error: { state: !0 },
  _ordersOpen: { state: !0 },
  _orders: { state: !0 }
};
let X = B;
function J(r, t) {
  return t == null ? "–" : C(r, String(t));
}
const W = class W extends b {
  constructor() {
    super(...arguments), this._targetMode = "duration", this._targetValue = 600, this._hardLimit = 3600, this._busy = !1, this._manualOpen = !1, this._historyOpen = !1, this._conflictPolicy = "start_now", this._history = [], this._historyOffset = 0, this._historyTotal = 0, this._historySource = "", this._historyResult = "";
  }
  static getConfigElement() {
    return document.createElement("irrigation-manager-zone-card-editor");
  }
  static getStubConfig() {
    return {
      type: "custom:irrigation-manager-zone-card",
      entity: ""
    };
  }
  setConfig(t) {
    this._config = { ...t };
  }
  getCardSize() {
    return 6;
  }
  metric(t, e) {
    return u`<div class="metric"><span>${t}</span><strong>${O(this.hass, e)}</strong></div>`;
  }
  context() {
    const t = G(this.hass, this._config), e = _(this.hass, t.zone_entity), i = z(e, "config_entry_id"), s = z(e, "zone_subentry_id");
    return i && s ? { config_entry_id: i, zone_subentry_id: s } : void 0;
  }
  async perform(t, e, i) {
    if (!(i && !window.confirm(i))) {
      this._busy = !0, this._error = void 0;
      try {
        await this.hass.callService(I, t, e);
      } catch (s) {
        this._error = `${o(this.hass, "action_failed")}: ${s instanceof Error ? s.message : String(s)}`;
      } finally {
        this._busy = !1;
      }
    }
  }
  async request() {
    const t = this.context();
    if (!t) {
      this._error = o(this.hass, "configuration_error");
      return;
    }
    if (!Number.isFinite(this._targetValue) || this._targetValue <= 0) {
      this._error = o(this.hass, "invalid_target");
      return;
    }
    if (this._targetMode === "amount" && (!Number.isFinite(this._hardLimit) || this._hardLimit <= 0)) {
      this._error = o(this.hass, "hard_limit_required");
      return;
    }
    const e = _(this.hass, G(this.hass, this._config).zone_entity), i = this._targetMode === "duration" ? U(e, "max_manual_duration_seconds") : U(e, "max_manual_volume_runtime_seconds"), s = this._targetMode === "duration" ? this._targetValue : this._hardLimit;
    if (i !== void 0 && s > i) {
      this._error = o(this.hass, "invalid_target");
      return;
    }
    const n = this._targetMode === "duration" ? { duration: this._targetValue } : { amount: this._targetValue, hard_time_limit: this._hardLimit }, a = e?.attributes.active_execution === !0;
    await this.perform("start_manual_from_card", {
      ...t,
      ...n,
      conflict_policy: a ? this._conflictPolicy : "start_now"
    }), this._error || (this._manualOpen = !1);
  }
  openManual(t) {
    this._conflictPolicy = t?.attributes.active_execution === !0 ? "stop_active" : "start_now", this._manualOpen = !0, this._error = void 0;
  }
  async loadHistory(t = 0) {
    const e = this.context();
    if (e) {
      this._historyOpen = !0, this._busy = !0, this._error = void 0;
      try {
        const i = { ...e, offset: t, limit: 20 };
        this._historySource && (i.source = this._historySource), this._historyResult && (i.result = this._historyResult);
        const s = await this.hass.callService(
          I,
          "list_zone_history",
          i,
          void 0,
          !0
        );
        this._history = s.items ?? [], this._historyOffset = s.offset ?? t, this._historyTotal = s.total ?? 0;
      } catch (i) {
        this._error = `${o(this.hass, "action_failed")}: ${i instanceof Error ? i.message : String(i)}`;
      } finally {
        this._busy = !1;
      }
    }
  }
  historyTarget(t) {
    return `${String(t.target_value)} ${t.target_type === "volume" ? o(this.hass, "liters") : o(this.hass, "seconds")}`;
  }
  render() {
    if (!this.hass || !this._config) return d;
    const t = G(this.hass, this._config);
    if (!t.zone_entity || !_(this.hass, t.zone_entity))
      return u`<ha-card><div class="card"><div class="warning"><ha-icon icon="mdi:water-alert"></ha-icon><span>${o(this.hass, "missing")}</span></div></div></ha-card>`;
    const e = _(this.hass, t.zone_entity), i = _(this.hass, t.status_entity), s = this.context(), n = typeof e?.attributes.card_name == "string" ? e.attributes.card_name : e?.attributes.friendly_name ?? o(this.hass, "zone"), a = ["disabled", "installation_disabled", "safety_lock", "needs_reconfiguration"].includes(
      i?.state ?? ""
    ), c = U(e, "max_manual_duration_seconds") ?? 604800, h = U(e, "max_manual_volume_runtime_seconds") ?? 604800;
    return u`
      <ha-card>
        <div class="card">
          <header>
            <div class="hero">
              <ha-icon .icon=${At(i?.state ?? "unknown")}></ha-icon>
              <div>
                <h2>${n}</h2>
                <strong>${O(this.hass, i)}</strong>
              </div>
            </div>
          </header>

          <div class="metrics">
            ${this.metric(o(this.hass, "status"), i)}
            ${this.metric(o(this.hass, e?.attributes.volume_control_available === !0 ? "water_today" : "runtime_today"), _(this.hass, e?.attributes.volume_control_available === !0 ? t.water_today_entity : t.runtime_today_entity))}
            ${this.metric(o(this.hass, e?.attributes.volume_control_available === !0 ? "water_month" : "runtime_month"), _(this.hass, e?.attributes.volume_control_available === !0 ? t.water_month_entity : t.runtime_month_entity))}
            ${this.metric(o(this.hass, "next"), _(this.hass, t.next_irrigation_entity))}
          </div>

          ${this._error ? u`<div class="error" role="alert">${this._error}</div>` : d}
          <div class="actions">
            <button class="primary" data-testid="manual-irrigation" ?disabled=${this._busy || a || !s} @click=${() => this.openManual(e)}><ha-icon icon="mdi:sprinkler-variant"></ha-icon>${o(this.hass, "manual_water")}</button>
            <button data-testid="show-history" ?disabled=${this._busy || !s} @click=${() => this.loadHistory(0)}><ha-icon icon="mdi:history"></ha-icon>${o(this.hass, "show_history")}</button>
          </div>
          ${this._manualOpen ? u`
            <dialog open aria-labelledby="manual-title">
              <div class="dialog-header"><h2 id="manual-title">${o(this.hass, "manual_water")}</h2><button class="icon-button" aria-label=${o(this.hass, "close")} @click=${() => {
      this._manualOpen = !1;
    }}>×</button></div>
              <div class="form-grid">
                <label class="field"><span>${o(this.hass, "target")}</span><select data-testid="target-mode" .value=${this._targetMode} @change=${(l) => {
      this._targetMode = l.target.value;
    }}><option value="duration">${o(this.hass, "duration_mode")}</option>${e?.attributes.volume_control_available === !0 ? u`<option value="amount">${o(this.hass, "amount_mode")}</option>` : d}</select></label>
                <label class="field"><span>${this._targetMode === "duration" ? o(this.hass, "duration") : o(this.hass, "amount")}</span><input data-testid="manual-target" type="number" min="0.001" max=${this._targetMode === "duration" ? String(c) : "1000000"} step=${this._targetMode === "duration" ? "1" : "0.1"} .value=${String(this._targetValue)} @input=${(l) => {
      this._targetValue = Number(l.target.value);
    }} /><span>${this._targetMode === "duration" ? o(this.hass, "seconds") : o(this.hass, "liters")}</span></label>
                ${this._targetMode === "amount" ? u`<label class="field"><span>${o(this.hass, "hard_limit")}</span><input data-testid="hard-limit" type="number" min="0.001" max=${String(h)} step="1" .value=${String(this._hardLimit)} @input=${(l) => {
      this._hardLimit = Number(l.target.value);
    }} /><span>${o(this.hass, "seconds")}</span></label>` : d}
                ${e?.attributes.active_execution === !0 ? u`<label class="field"><span>${o(this.hass, "active_execution_choice")}</span><select data-testid="conflict-policy" .value=${this._conflictPolicy} @change=${(l) => {
      this._conflictPolicy = l.target.value;
    }}><option value="stop_active">${o(this.hass, "stop_active_start_now")}</option><option value="priority_next">${o(this.hass, "finish_then_priority")}</option></select></label>` : d}
              </div>
              ${this._error ? u`<div class="error" role="alert">${this._error}</div>` : d}
              <div class="actions dialog-actions"><button data-testid="submit-manual" class="primary" ?disabled=${this._busy} @click=${this.request}>${o(this.hass, "start")}</button></div>
            </dialog>` : d}
          ${this._historyOpen ? u`
            <dialog open aria-labelledby="history-title">
              <div class="dialog-header"><h2 id="history-title">${o(this.hass, "irrigation_history")}</h2><button class="icon-button" aria-label=${o(this.hass, "close")} @click=${() => {
      this._historyOpen = !1;
    }}>×</button></div>
              <div class="filters"><label class="field"><span>${o(this.hass, "source")}</span><select .value=${this._historySource} @change=${(l) => {
      this._historySource = l.target.value, this.loadHistory(0);
    }}><option value="">${o(this.hass, "all")}</option><option value="manual">${o(this.hass, "manual")}</option><option value="automatic">${o(this.hass, "automatic")}</option></select></label><label class="field"><span>${o(this.hass, "result")}</span><select .value=${this._historyResult} @change=${(l) => {
      this._historyResult = l.target.value, this.loadHistory(0);
    }}><option value="">${o(this.hass, "all")}</option><option value="completed">${o(this.hass, "completed")}</option><option value="failed">${o(this.hass, "failed")}</option><option value="cancelled">${o(this.hass, "cancelled")}</option></select></label></div>
              ${this._busy ? u`<p aria-live="polite">${o(this.hass, "loading")}</p>` : u`<div class="history-list">${this._history.map((l) => u`<article><strong>${this.historyTarget(l)}</strong><span>${String(l.started_at)} – ${String(l.ended_at ?? "")}</span><span>${J(this.hass, l.source)} · ${J(this.hass, l.result)} · ${String(l.actual_duration)} s${l.actual_water == null ? "" : ` · ${String(l.actual_water)} L`} · ${J(this.hass, l.completion_reason)}</span></article>`)}</div>`}
              <div class="actions"><button ?disabled=${this._busy || this._historyOffset === 0} @click=${() => this.loadHistory(Math.max(0, this._historyOffset - 20))}>${o(this.hass, "previous")}</button><span>${this._historyTotal === 0 ? 0 : this._historyOffset + 1}–${Math.min(this._historyOffset + this._history.length, this._historyTotal)} / ${this._historyTotal}</span><button ?disabled=${this._busy || this._historyOffset + this._history.length >= this._historyTotal} @click=${() => this.loadHistory(this._historyOffset + 20)}>${o(this.hass, "next_page")}</button></div>
            </dialog>` : d}
        </div>
      </ha-card>
    `;
  }
};
W.styles = Et, W.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 },
  _targetMode: { state: !0 },
  _targetValue: { state: !0 },
  _hardLimit: { state: !0 },
  _busy: { state: !0 },
  _error: { state: !0 },
  _manualOpen: { state: !0 },
  _historyOpen: { state: !0 },
  _conflictPolicy: { state: !0 },
  _history: { state: !0 },
  _historyOffset: { state: !0 },
  _historyTotal: { state: !0 },
  _historySource: { state: !0 },
  _historyResult: { state: !0 }
};
let Y = W;
const ne = [
  ["irrigation-manager-overview-card", X],
  ["irrigation-manager-zone-card", Y],
  ["irrigation-manager-overview-card-editor", se],
  ["irrigation-manager-zone-card-editor", re]
];
for (const [r, t] of ne)
  customElements.get(r) || customElements.define(r, t);
window.customCards = window.customCards ?? [];
for (const r of [
  {
    type: "irrigation-manager-overview-card",
    name: "Irrigation Manager Overview",
    description: "Installation status, irrigation schedule, usage and emergency stop.",
    preview: !0
  },
  {
    type: "irrigation-manager-zone-card",
    name: "Irrigation Manager Zone",
    description: "Effective zone status, irrigation schedule, manual watering and history.",
    preview: !0
  }
])
  window.customCards.some((t) => t.type === r.type) || window.customCards.push(r);
