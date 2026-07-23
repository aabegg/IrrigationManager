const L = globalThis, at = L.ShadowRoot && (L.ShadyCSS === void 0 || L.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype, ot = /* @__PURE__ */ Symbol(), mt = /* @__PURE__ */ new WeakMap();
let Nt = class {
  constructor(t, e, i) {
    if (this._$cssResult$ = !0, i !== ot) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
    this.cssText = t, this.t = e;
  }
  get styleSheet() {
    let t = this.o;
    const e = this.t;
    if (at && t === void 0) {
      const i = e !== void 0 && e.length === 1;
      i && (t = mt.get(e)), t === void 0 && ((this.o = t = new CSSStyleSheet()).replaceSync(this.cssText), i && mt.set(e, t));
    }
    return t;
  }
  toString() {
    return this.cssText;
  }
};
const Gt = (s) => new Nt(typeof s == "string" ? s : s + "", void 0, ot), Tt = (s, ...t) => {
  const e = s.length === 1 ? s[0] : t.reduce((i, n, o) => i + ((r) => {
    if (r._$cssResult$ === !0) return r.cssText;
    if (typeof r == "number") return r;
    throw Error("Value passed to 'css' function must be a 'css' function result: " + r + ". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.");
  })(n) + s[o + 1], s[0]);
  return new Nt(e, s, ot);
}, Jt = (s, t) => {
  if (at) s.adoptedStyleSheets = t.map((e) => e instanceof CSSStyleSheet ? e : e.styleSheet);
  else for (const e of t) {
    const i = document.createElement("style"), n = L.litNonce;
    n !== void 0 && i.setAttribute("nonce", n), i.textContent = e.cssText, s.appendChild(i);
  }
}, gt = at ? (s) => s : (s) => s instanceof CSSStyleSheet ? ((t) => {
  let e = "";
  for (const i of t.cssRules) e += i.cssText;
  return Gt(e);
})(s) : s;
const { is: Qt, defineProperty: Yt, getOwnPropertyDescriptor: Xt, getOwnPropertyNames: te, getOwnPropertySymbols: ee, getPrototypeOf: ie } = Object, F = globalThis, ft = F.trustedTypes, se = ft ? ft.emptyScript : "", ne = F.reactiveElementPolyfillSupport, T = (s, t) => s, Y = { toAttribute(s, t) {
  switch (t) {
    case Boolean:
      s = s ? se : null;
      break;
    case Object:
    case Array:
      s = s == null ? s : JSON.stringify(s);
  }
  return s;
}, fromAttribute(s, t) {
  let e = s;
  switch (t) {
    case Boolean:
      e = s !== null;
      break;
    case Number:
      e = s === null ? null : Number(s);
      break;
    case Object:
    case Array:
      try {
        e = JSON.parse(s);
      } catch {
        e = null;
      }
  }
  return e;
} }, Pt = (s, t) => !Qt(s, t), yt = { attribute: !0, type: String, converter: Y, reflect: !1, useDefault: !1, hasChanged: Pt };
Symbol.metadata ??= /* @__PURE__ */ Symbol("metadata"), F.litPropertyMetadata ??= /* @__PURE__ */ new WeakMap();
let z = class extends HTMLElement {
  static addInitializer(t) {
    this._$Ei(), (this.l ??= []).push(t);
  }
  static get observedAttributes() {
    return this.finalize(), this._$Eh && [...this._$Eh.keys()];
  }
  static createProperty(t, e = yt) {
    if (e.state && (e.attribute = !1), this._$Ei(), this.prototype.hasOwnProperty(t) && ((e = Object.create(e)).wrapped = !0), this.elementProperties.set(t, e), !e.noAccessor) {
      const i = /* @__PURE__ */ Symbol(), n = this.getPropertyDescriptor(t, i, e);
      n !== void 0 && Yt(this.prototype, t, n);
    }
  }
  static getPropertyDescriptor(t, e, i) {
    const { get: n, set: o } = Xt(this.prototype, t) ?? { get() {
      return this[e];
    }, set(r) {
      this[e] = r;
    } };
    return { get: n, set(r) {
      const u = n?.call(this);
      o?.call(this, r), this.requestUpdate(t, u, i);
    }, configurable: !0, enumerable: !0 };
  }
  static getPropertyOptions(t) {
    return this.elementProperties.get(t) ?? yt;
  }
  static _$Ei() {
    if (this.hasOwnProperty(T("elementProperties"))) return;
    const t = ie(this);
    t.finalize(), t.l !== void 0 && (this.l = [...t.l]), this.elementProperties = new Map(t.elementProperties);
  }
  static finalize() {
    if (this.hasOwnProperty(T("finalized"))) return;
    if (this.finalized = !0, this._$Ei(), this.hasOwnProperty(T("properties"))) {
      const e = this.properties, i = [...te(e), ...ee(e)];
      for (const n of i) this.createProperty(n, e[n]);
    }
    const t = this[Symbol.metadata];
    if (t !== null) {
      const e = litPropertyMetadata.get(t);
      if (e !== void 0) for (const [i, n] of e) this.elementProperties.set(i, n);
    }
    this._$Eh = /* @__PURE__ */ new Map();
    for (const [e, i] of this.elementProperties) {
      const n = this._$Eu(e, i);
      n !== void 0 && this._$Eh.set(n, e);
    }
    this.elementStyles = this.finalizeStyles(this.styles);
  }
  static finalizeStyles(t) {
    const e = [];
    if (Array.isArray(t)) {
      const i = new Set(t.flat(1 / 0).reverse());
      for (const n of i) e.unshift(gt(n));
    } else t !== void 0 && e.push(gt(t));
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
    return Jt(t, this.constructor.elementStyles), t;
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
    const i = this.constructor.elementProperties.get(t), n = this.constructor._$Eu(t, i);
    if (n !== void 0 && i.reflect === !0) {
      const o = (i.converter?.toAttribute !== void 0 ? i.converter : Y).toAttribute(e, i.type);
      this._$Em = t, o == null ? this.removeAttribute(n) : this.setAttribute(n, o), this._$Em = null;
    }
  }
  _$AK(t, e) {
    const i = this.constructor, n = i._$Eh.get(t);
    if (n !== void 0 && this._$Em !== n) {
      const o = i.getPropertyOptions(n), r = typeof o.converter == "function" ? { fromAttribute: o.converter } : o.converter?.fromAttribute !== void 0 ? o.converter : Y;
      this._$Em = n;
      const u = r.fromAttribute(e, o.type);
      this[n] = u ?? this._$Ej?.get(n) ?? u, this._$Em = null;
    }
  }
  requestUpdate(t, e, i, n = !1, o) {
    if (t !== void 0) {
      const r = this.constructor;
      if (n === !1 && (o = this[t]), i ??= r.getPropertyOptions(t), !((i.hasChanged ?? Pt)(o, e) || i.useDefault && i.reflect && o === this._$Ej?.get(t) && !this.hasAttribute(r._$Eu(t, i)))) return;
      this.C(t, e, i);
    }
    this.isUpdatePending === !1 && (this._$ES = this._$EP());
  }
  C(t, e, { useDefault: i, reflect: n, wrapped: o }, r) {
    i && !(this._$Ej ??= /* @__PURE__ */ new Map()).has(t) && (this._$Ej.set(t, r ?? e ?? this[t]), o !== !0 || r !== void 0) || (this._$AL.has(t) || (this.hasUpdated || i || (e = void 0), this._$AL.set(t, e)), n === !0 && this._$Em !== t && (this._$Eq ??= /* @__PURE__ */ new Set()).add(t));
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
        for (const [n, o] of this._$Ep) this[n] = o;
        this._$Ep = void 0;
      }
      const i = this.constructor.elementProperties;
      if (i.size > 0) for (const [n, o] of i) {
        const { wrapped: r } = o, u = this[n];
        r !== !0 || this._$AL.has(n) || u === void 0 || this.C(n, void 0, o, u);
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
z.elementStyles = [], z.shadowRootOptions = { mode: "open" }, z[T("elementProperties")] = /* @__PURE__ */ new Map(), z[T("finalized")] = /* @__PURE__ */ new Map(), ne?.({ ReactiveElement: z }), (F.reactiveElementVersions ??= []).push("2.1.2");
const rt = globalThis, $t = (s) => s, H = rt.trustedTypes, vt = H ? H.createPolicy("lit-html", { createHTML: (s) => s }) : void 0, Ot = "$lit$", w = `lit$${Math.random().toFixed(9).slice(2)}$`, Rt = "?" + w, ae = `<${Rt}>`, E = document, P = () => E.createComment(""), O = (s) => s === null || typeof s != "object" && typeof s != "function", ct = Array.isArray, oe = (s) => ct(s) || typeof s?.[Symbol.iterator] == "function", J = `[\x20\t\n\f\r]`, N = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g, bt = /-->/g, wt = />/g, A = RegExp(`>|${J}(?:([^\\s"'>=/]+)(${J}*=${J}*(?:[^\x20\t\n\f\r"'\`<>=]|("|')|))|$)`, "g"), xt = /'/g, At = /"/g, Dt = /^(?:script|style|textarea|title)$/i, re = (s) => (t, ...e) => ({ _$litType$: s, strings: t, values: e }), l = re(1), M = /* @__PURE__ */ Symbol.for("lit-noChange"), c = /* @__PURE__ */ Symbol.for("lit-nothing"), kt = /* @__PURE__ */ new WeakMap(), k = E.createTreeWalker(E, 129);
function Ut(s, t) {
  if (!ct(s) || !s.hasOwnProperty("raw")) throw Error("invalid template strings array");
  return vt !== void 0 ? vt.createHTML(t) : t;
}
const ce = (s, t) => {
  const e = s.length - 1, i = [];
  let n, o = t === 2 ? "<svg>" : t === 3 ? "<math>" : "", r = N;
  for (let u = 0; u < e; u++) {
    const d = s[u];
    let p, m, _ = -1, f = 0;
    for (; f < d.length && (r.lastIndex = f, m = r.exec(d), m !== null); ) f = r.lastIndex, r === N ? m[1] === "!--" ? r = bt : m[1] !== void 0 ? r = wt : m[2] !== void 0 ? (Dt.test(m[2]) && (n = RegExp("</" + m[2], "g")), r = A) : m[3] !== void 0 && (r = A) : r === A ? m[0] === ">" ? (r = n ?? N, _ = -1) : m[1] === void 0 ? _ = -2 : (_ = r.lastIndex - m[2].length, p = m[1], r = m[3] === void 0 ? A : m[3] === '"' ? At : xt) : r === At || r === xt ? r = A : r === bt || r === wt ? r = N : (r = A, n = void 0);
    const $ = r === A && s[u + 1].startsWith("/>") ? " " : "";
    o += r === N ? d + ae : _ >= 0 ? (i.push(p), d.slice(0, _) + Ot + d.slice(_) + w + $) : d + w + (_ === -2 ? u : $);
  }
  return [Ut(s, o + (s[e] || "<?>") + (t === 2 ? "</svg>" : t === 3 ? "</math>" : "")), i];
};
class R {
  constructor({ strings: t, _$litType$: e }, i) {
    let n;
    this.parts = [];
    let o = 0, r = 0;
    const u = t.length - 1, d = this.parts, [p, m] = ce(t, e);
    if (this.el = R.createElement(p, i), k.currentNode = this.el.content, e === 2 || e === 3) {
      const _ = this.el.content.firstChild;
      _.replaceWith(..._.childNodes);
    }
    for (; (n = k.nextNode()) !== null && d.length < u; ) {
      if (n.nodeType === 1) {
        if (n.hasAttributes()) for (const _ of n.getAttributeNames()) if (_.endsWith(Ot)) {
          const f = m[r++], $ = n.getAttribute(_).split(w), g = /([.?@])?(.*)/.exec(f);
          d.push({ type: 1, index: o, name: g[2], strings: $, ctor: g[1] === "." ? he : g[1] === "?" ? de : g[1] === "@" ? ue : K }), n.removeAttribute(_);
        } else _.startsWith(w) && (d.push({ type: 6, index: o }), n.removeAttribute(_));
        if (Dt.test(n.tagName)) {
          const _ = n.textContent.split(w), f = _.length - 1;
          if (f > 0) {
            n.textContent = H ? H.emptyScript : "";
            for (let $ = 0; $ < f; $++) n.append(_[$], P()), k.nextNode(), d.push({ type: 2, index: ++o });
            n.append(_[f], P());
          }
        }
      } else if (n.nodeType === 8) if (n.data === Rt) d.push({ type: 2, index: o });
      else {
        let _ = -1;
        for (; (_ = n.data.indexOf(w, _ + 1)) !== -1; ) d.push({ type: 7, index: o }), _ += w.length - 1;
      }
      o++;
    }
  }
  static createElement(t, e) {
    const i = E.createElement("template");
    return i.innerHTML = t, i;
  }
}
function C(s, t, e = s, i) {
  if (t === M) return t;
  let n = i !== void 0 ? e._$Co?.[i] : e._$Cl;
  const o = O(t) ? void 0 : t._$litDirective$;
  return n?.constructor !== o && (n?._$AO?.(!1), o === void 0 ? n = void 0 : (n = new o(s), n._$AT(s, e, i)), i !== void 0 ? (e._$Co ??= [])[i] = n : e._$Cl = n), n !== void 0 && (t = C(s, n._$AS(s, t.values), n, i)), t;
}
class le {
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
    const { el: { content: e }, parts: i } = this._$AD, n = (t?.creationScope ?? E).importNode(e, !0);
    k.currentNode = n;
    let o = k.nextNode(), r = 0, u = 0, d = i[0];
    for (; d !== void 0; ) {
      if (r === d.index) {
        let p;
        d.type === 2 ? p = new U(o, o.nextSibling, this, t) : d.type === 1 ? p = new d.ctor(o, d.name, d.strings, this, t) : d.type === 6 && (p = new _e(o, this, t)), this._$AV.push(p), d = i[++u];
      }
      r !== d?.index && (o = k.nextNode(), r++);
    }
    return k.currentNode = E, n;
  }
  p(t) {
    let e = 0;
    for (const i of this._$AV) i !== void 0 && (i.strings !== void 0 ? (i._$AI(t, i, e), e += i.strings.length - 2) : i._$AI(t[e])), e++;
  }
}
class U {
  get _$AU() {
    return this._$AM?._$AU ?? this._$Cv;
  }
  constructor(t, e, i, n) {
    this.type = 2, this._$AH = c, this._$AN = void 0, this._$AA = t, this._$AB = e, this._$AM = i, this.options = n, this._$Cv = n?.isConnected ?? !0;
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
    t = C(this, t, e), O(t) ? t === c || t == null || t === "" ? (this._$AH !== c && this._$AR(), this._$AH = c) : t !== this._$AH && t !== M && this._(t) : t._$litType$ !== void 0 ? this.$(t) : t.nodeType !== void 0 ? this.T(t) : oe(t) ? this.k(t) : this._(t);
  }
  O(t) {
    return this._$AA.parentNode.insertBefore(t, this._$AB);
  }
  T(t) {
    this._$AH !== t && (this._$AR(), this._$AH = this.O(t));
  }
  _(t) {
    this._$AH !== c && O(this._$AH) ? this._$AA.nextSibling.data = t : this.T(E.createTextNode(t)), this._$AH = t;
  }
  $(t) {
    const { values: e, _$litType$: i } = t, n = typeof i == "number" ? this._$AC(t) : (i.el === void 0 && (i.el = R.createElement(Ut(i.h, i.h[0]), this.options)), i);
    if (this._$AH?._$AD === n) this._$AH.p(e);
    else {
      const o = new le(n, this), r = o.u(this.options);
      o.p(e), this.T(r), this._$AH = o;
    }
  }
  _$AC(t) {
    let e = kt.get(t.strings);
    return e === void 0 && kt.set(t.strings, e = new R(t)), e;
  }
  k(t) {
    ct(this._$AH) || (this._$AH = [], this._$AR());
    const e = this._$AH;
    let i, n = 0;
    for (const o of t) n === e.length ? e.push(i = new U(this.O(P()), this.O(P()), this, this.options)) : i = e[n], i._$AI(o), n++;
    n < e.length && (this._$AR(i && i._$AB.nextSibling, n), e.length = n);
  }
  _$AR(t = this._$AA.nextSibling, e) {
    for (this._$AP?.(!1, !0, e); t !== this._$AB; ) {
      const i = $t(t).nextSibling;
      $t(t).remove(), t = i;
    }
  }
  setConnected(t) {
    this._$AM === void 0 && (this._$Cv = t, this._$AP?.(t));
  }
}
class K {
  get tagName() {
    return this.element.tagName;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  constructor(t, e, i, n, o) {
    this.type = 1, this._$AH = c, this._$AN = void 0, this.element = t, this.name = e, this._$AM = n, this.options = o, i.length > 2 || i[0] !== "" || i[1] !== "" ? (this._$AH = Array(i.length - 1).fill(new String()), this.strings = i) : this._$AH = c;
  }
  _$AI(t, e = this, i, n) {
    const o = this.strings;
    let r = !1;
    if (o === void 0) t = C(this, t, e, 0), r = !O(t) || t !== this._$AH && t !== M, r && (this._$AH = t);
    else {
      const u = t;
      let d, p;
      for (t = o[0], d = 0; d < o.length - 1; d++) p = C(this, u[i + d], e, d), p === M && (p = this._$AH[d]), r ||= !O(p) || p !== this._$AH[d], p === c ? t = c : t !== c && (t += (p ?? "") + o[d + 1]), this._$AH[d] = p;
    }
    r && !n && this.j(t);
  }
  j(t) {
    t === c ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, t ?? "");
  }
}
class he extends K {
  constructor() {
    super(...arguments), this.type = 3;
  }
  j(t) {
    this.element[this.name] = t === c ? void 0 : t;
  }
}
class de extends K {
  constructor() {
    super(...arguments), this.type = 4;
  }
  j(t) {
    this.element.toggleAttribute(this.name, !!t && t !== c);
  }
}
class ue extends K {
  constructor(t, e, i, n, o) {
    super(t, e, i, n, o), this.type = 5;
  }
  _$AI(t, e = this) {
    if ((t = C(this, t, e, 0) ?? c) === M) return;
    const i = this._$AH, n = t === c && i !== c || t.capture !== i.capture || t.once !== i.once || t.passive !== i.passive, o = t !== c && (i === c || n);
    n && this.element.removeEventListener(this.name, this, i), o && this.element.addEventListener(this.name, this, t), this._$AH = t;
  }
  handleEvent(t) {
    typeof this._$AH == "function" ? this._$AH.call(this.options?.host ?? this.element, t) : this._$AH.handleEvent(t);
  }
}
class _e {
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
const pe = rt.litHtmlPolyfillSupport;
pe?.(R, U), (rt.litHtmlVersions ??= []).push("3.3.3");
const me = (s, t, e) => {
  const i = e?.renderBefore ?? t;
  let n = i._$litPart$;
  if (n === void 0) {
    const o = e?.renderBefore ?? null;
    i._$litPart$ = n = new U(t.insertBefore(P(), o), o, void 0, e ?? {});
  }
  return n._$AI(s), n;
};
const lt = globalThis;
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
    this.hasUpdated || (this.renderOptions.isConnected = this.isConnected), super.update(t), this._$Do = me(e, this.renderRoot, this.renderOptions);
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
S._$litElement$ = !0, S.finalized = !0, lt.litElementHydrateSupport?.({ LitElement: S });
const ge = lt.litElementPolyfillSupport;
ge?.({ LitElement: S });
(lt.litElementVersions ??= []).push("4.2.2");
const It = "irrigation_manager", fe = "create_manual", ye = /* @__PURE__ */ new Set(["unknown", "unavailable"]), $e = {
  status: "status_entity",
  emergency: "emergency_entity",
  lock: "lock_entity",
  active_zone: "active_zone_entity",
  dose: "dose_entity",
  pending: "pending_entity",
  next: "next_entity",
  today_consumption: "today_consumption_entity",
  month_consumption: "month_consumption_entity",
  model_quality: "model_quality_entity",
  winter: "winter_entity",
  maintenance: "maintenance_entity",
  automation_release: "automation_release_entity",
  maintenance_due: "maintenance_due_entity"
}, ve = {
  zone: "zone_entity",
  automation_needed: "automation_needed_entity",
  safety_lock: "safety_lock_entity",
  deficit: "deficit_entity",
  target: "target_entity",
  planning_reason: "planning_reason_entity",
  next_window: "next_window_entity",
  last_delivered: "last_delivered_entity",
  last_duration: "last_duration_entity",
  quality: "quality_entity",
  status: "status_entity",
  automation_release: "automation_release_entity",
  archived: "archived_entity",
  coverage: "coverage_entity",
  expected_flow: "expected_flow_entity",
  actual_flow: "actual_flow_entity",
  flow_deviation: "flow_deviation_entity",
  calculation: "calculation_entity"
}, be = {
  active_zone: "active_zone_entity",
  dose: "request_entity",
  lock: "installation_safety_lock_entity"
};
function D(s, t) {
  const e = s?.attributes[t];
  return !e || typeof e != "object" || Array.isArray(e) ? {} : Object.fromEntries(
    Object.entries(e).filter(
      (i) => typeof i[1] == "string" && i[1].includes(".")
    )
  );
}
function X(s, t, e) {
  const i = { ...s };
  for (const [n, o] of Object.entries(e)) {
    const u = s[o] || t[n];
    u && Object.assign(i, { [o]: u });
  }
  return i;
}
function St(s, t) {
  if (!t.configuration_mode && !t.installation && t.status_entity) return t;
  const e = t.installation ? Lt(s, "installation", t.installation) : h(s, t.status_entity);
  return X(t, D(e, "card_entities"), $e);
}
function I(s, t) {
  if (!t.configuration_mode && !t.zone && t.zone_entity) return t;
  const e = t.zone ? Lt(s, "zone", t.zone) : h(s, t.zone_entity);
  let i = X(t, D(e, "card_entities"), ve);
  return i = X(
    i,
    D(e, "installation_card_entities"),
    be
  ), !i.zone_entity && e && (i.zone_entity = e.entity_id), i;
}
function Lt(s, t, e) {
  return Object.values(s.states).find((i) => tt(i, t) === e);
}
function tt(s, t) {
  const e = s.attributes.config_entry_id;
  if (typeof e != "string") return;
  if (t === "installation")
    return D(s, "card_entities").status === s.entity_id ? e : void 0;
  const i = s.attributes.zone_subentry_id;
  return typeof i == "string" && Object.keys(D(s, "card_entities")).length > 0 ? `${e}:${i}` : void 0;
}
function ht(s, t) {
  return s.configuration_mode ? s.configuration_mode : t.some((e) => !!s[e]) ? "expert" : "simple";
}
function we(s, t) {
  return Object.values(s.states).filter((e) => tt(e, t) !== void 0).map((e) => ({
    value: tt(e, t),
    label: typeof e.attributes.card_name == "string" && e.attributes.card_name || e.attributes.friendly_name || e.entity_id
  })).sort((e, i) => e.label.localeCompare(i.label, s.language));
}
function h(s, t) {
  return t ? s.states[t] : void 0;
}
function B(s) {
  return !!(s && !ye.has(s.state));
}
function y(s, t) {
  const e = s?.attributes[t];
  return typeof e == "string" && e ? e : void 0;
}
function Et(s, t) {
  const e = s?.attributes[t];
  return typeof e == "number" && Number.isFinite(e) ? e : void 0;
}
function Q(s, t) {
  if (!t || y(s, "zone_subentry_id") !== t)
    return;
  const e = y(s, "request_id"), i = y(s, "execution_id");
  return e || i ? { requestId: e, executionId: i } : void 0;
}
function Ht(s) {
  const t = Et(s, "target_value"), e = Et(s, "remaining_value");
  if (!(t === void 0 || e === void 0 || t <= 0))
    return Math.max(0, Math.min(100, (t - e) / t * 100));
}
function Bt(s) {
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
  }[s] ?? "mdi:information-outline";
}
function xe(s, t) {
  s.dispatchEvent(
    new CustomEvent("config-changed", {
      detail: { config: t },
      bubbles: !0,
      composed: !0
    })
  );
}
const Vt = {
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
    installation_safety_lock: "Installation safety lock",
    zone_safety_lock: "Zone safety lock",
    lock_reason: "Reason",
    lock_occurred_at: "Occurred",
    reset_safety: "Reset safety lock",
    confirm_reset_safety: "Did you inspect the installation, confirm all valves are closed, and want to reset this safety lock?",
    unexpectedly_opened: "was opened unexpectedly",
    unexpectedly_opened_during_startup: "was unexpectedly open during startup",
    unexpectedly_closed: "closed unexpectedly during irrigation",
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
    history: "History",
    configuration_mode: "Configuration",
    simple: "Simple",
    expert: "Expert",
    simple_description: "Select one installation or zone. Related entities are resolved automatically.",
    expert_description: "Select individual entities. Explicit selections override automatic resolution.",
    installation: "Irrigation installation"
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
    installation_safety_lock: "Sicherheitssperre der Anlage",
    zone_safety_lock: "Sicherheitssperre der Zone",
    lock_reason: "Ursache",
    lock_occurred_at: "Eingetreten",
    reset_safety: "Sperre zurücksetzen",
    confirm_reset_safety: "Hast du die Anlage kontrolliert, alle Ventile als geschlossen bestätigt und möchtest diese Sicherheitssperre zurücksetzen?",
    unexpectedly_opened: "wurde unerwartet geöffnet",
    unexpectedly_opened_during_startup: "war beim Start unerwartet geöffnet",
    unexpectedly_closed: "wurde während der Bewässerung unerwartet geschlossen",
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
    history: "Historie",
    configuration_mode: "Konfiguration",
    simple: "Einfach",
    expert: "Experte",
    simple_description: "Eine Anlage oder Zone auswählen. Zugehörige Entities werden automatisch ermittelt.",
    expert_description: "Entities einzeln auswählen. Explizite Auswahlen überschreiben die automatische Ermittlung.",
    installation: "Bewässerungsanlage"
  }
};
function a(s, t) {
  const e = s.language?.toLowerCase().startsWith("de") ? "de" : "en";
  return Vt[e][t];
}
function Wt(s, t) {
  return t in Vt.en ? a(s, t) : t.replaceAll("_", " ");
}
function x(s, t) {
  if (!t) return a(s, "missing");
  if (t.state === "unavailable") return a(s, "unavailable");
  if (t.state === "unknown" || t.state === "") return a(s, "unknown");
  if (s.formatEntityState) return s.formatEntityState(t);
  const e = t.attributes.unit_of_measurement;
  return `${Wt(s, t.state)}${e ? ` ${e}` : ""}`;
}
const jt = Tt`
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
`, Ae = Tt`
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
`, et = [
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
], it = [
  ["zone_entity", "Zone total / action identity"],
  ["automation_needed_entity", "Automatic demand"],
  ["safety_lock_entity", "Zone safety lock"],
  ["installation_safety_lock_entity", "Installation safety lock"],
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
], zt = et.map(([s]) => s), Mt = it.map(([s]) => s), ke = {
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
}, Se = ["active", "pending", "next", "today", "month", "quality", "maintenance"], Ee = ["stop", "emergency", "suspend", "resume"], ze = ["status", "balance", "next", "total", "recent", "quality", "calculation", "flow", "history"], Me = ["create", "start", "pause", "resume", "stop", "stop_skip", "suspend", "resume_auto", "archive", "restore"], W = class W extends S {
  setConfig(t) {
    this._config = { ...t };
  }
  updateValue(t, e) {
    const i = { ...this._config, [t]: e || void 0 };
    e || delete i[t], this._config = i, xe(this, i);
  }
  entitySelector(t, e, i) {
    const n = this.hass.language.toLowerCase().startsWith("de") ? ke[e] ?? e : e;
    return l`
      <label class="selector">
        <span>${n}${i ? " *" : ""}</span>
        <ha-selector
          .hass=${this.hass}
          .selector=${{ entity: { filter: { integration: "irrigation_manager" } } }}
          .value=${this._config[t] ?? ""}
          @value-changed=${(o) => this.updateValue(t, o.detail.value)}
        ></ha-selector>
      </label>
    `;
  }
  displayMode() {
    return l`
      <label class="selector">
        <span>${a(this.hass, "display")}</span>
        <select
          .value=${this._config.display_mode ?? "detailed"}
          @change=${(t) => this.updateValue("display_mode", t.target.value)}
        >
          <option value="compact">${a(this.hass, "compact")}</option>
          <option value="detailed">${a(this.hass, "detailed")}</option>
        </select>
      </label>
    `;
  }
  configurationMode(t) {
    const e = ht(this._config, t);
    return l`
      <label class="selector">
        <span>${a(this.hass, "configuration_mode")}</span>
        <select
          data-testid="configuration-mode"
          .value=${e}
          @change=${(i) => this.updateValue("configuration_mode", i.target.value)}
        >
          <option value="simple">${a(this.hass, "simple")}</option>
          <option value="expert">${a(this.hass, "expert")}</option>
        </select>
        <small>${a(this.hass, e === "simple" ? "simple_description" : "expert_description")}</small>
      </label>
    `;
  }
  anchorSelector(t, e, i) {
    const n = we(this.hass, e);
    return l`
      <label class="selector">
        <span>${a(this.hass, e)}</span>
        <select
          data-testid="anchor-selector"
          .value=${String(this._config[t] ?? i ?? "")}
          @change=${(o) => this.updateValue(t, o.target.value)}
        >
          <option value="">${a(this.hass, "missing")}</option>
          ${n.map(
      (o) => l`<option value=${o.value}>${o.label}</option>`
    )}
        </select>
      </label>
    `;
  }
  choices(t, e) {
    const i = this._config[t] ?? e;
    return l`
      <div class="checks">
        ${e.map(
      (n) => l`
            <label class="check">
              <input
                type="checkbox"
                .checked=${i.includes(n)}
                @change=${(o) => {
        const r = o.target.checked;
        this.updateValue(
          t,
          r ? [...i, n] : i.filter((u) => u !== n)
        );
      }}
              />
              ${a(this.hass, n)}
            </label>
          `
    )}
      </div>
    `;
  }
};
W.styles = Ae, W.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 }
};
let V = W;
class Ce extends V {
  render() {
    if (!this.hass || !this._config) return c;
    const t = ht(this._config, zt);
    return l`
      <div class="editor">
        <section>${this.configurationMode(zt)}</section>
        ${t === "simple" ? l`<section>${this.anchorSelector("installation", "installation")}</section>` : l`
              <section>
                <h3>${a(this.hass, "required_entity")}</h3>
                ${this.entitySelector("status_entity", et[0][1], !0)}
              </section>
              <section>
                <h3>${a(this.hass, "optional_entities")}</h3>
                ${et.slice(1).map(([e, i]) => this.entitySelector(e, i, !1))}
              </section>
            `}
        <section>${this.displayMode()}</section>
        <section>
          <h3>${a(this.hass, "metrics")}</h3>
          ${this.choices("visible_metrics", Se)}
        </section>
        <section>
          <h3>${a(this.hass, "actions")}</h3>
          ${this.choices("visible_actions", Ee)}
        </section>
      </div>
    `;
  }
}
class qe extends V {
  render() {
    if (!this.hass || !this._config) return c;
    const t = ht(this._config, Mt);
    return l`
      <div class="editor">
        <section>${this.configurationMode(Mt)}</section>
        ${t === "simple" ? l`<section>${this.anchorSelector("zone", "zone")}</section>` : l`
              <section>
                <h3>${a(this.hass, "required_entity")}</h3>
                ${this.entitySelector("zone_entity", it[0][1], !0)}
              </section>
              <section>
                <h3>${a(this.hass, "optional_entities")}</h3>
                ${it.slice(1).map(([e, i]) => this.entitySelector(e, i, !1))}
              </section>
            `}
        <section>${this.displayMode()}</section>
        <section>
          <h3>${a(this.hass, "metrics")}</h3>
          ${this.choices("visible_metrics", ze)}
        </section>
        <section>
          <h3>${a(this.hass, "actions")}</h3>
          ${this.choices("visible_actions", Me)}
        </section>
      </div>
    `;
  }
}
const Ct = ["active", "pending", "next", "today", "month", "quality", "maintenance"], Ne = ["stop", "emergency", "suspend", "resume"], j = class j extends S {
  constructor() {
    super(...arguments), this._busy = !1;
  }
  static getConfigElement() {
    return document.createElement("irrigation-manager-overview-card-editor");
  }
  static getStubConfig() {
    return {
      type: "custom:irrigation-manager-overview-card",
      configuration_mode: "simple",
      installation: ""
    };
  }
  setConfig(t) {
    this._config = { ...t };
  }
  getCardSize() {
    return this._config?.display_mode === "compact" ? 3 : 5;
  }
  metric(t, e, i) {
    return (this._config.visible_metrics ?? Ct).includes(t) ? l`<div class="metric"><span>${e}</span><strong>${x(this.hass, i)}</strong></div>` : c;
  }
  async call(t, e, i = {}) {
    if (!window.confirm(e)) return;
    const n = St(this.hass, this._config), o = h(this.hass, n.status_entity), r = y(o, "config_entry_id");
    if (!r) {
      this._error = a(this.hass, "configuration_error");
      return;
    }
    this._busy = !0, this._error = void 0;
    try {
      await this.hass.callService(It, t, { config_entry_id: r, ...i });
    } catch (u) {
      this._error = `${a(this.hass, "action_failed")}: ${u instanceof Error ? u.message : String(u)}`;
    } finally {
      this._busy = !1;
    }
  }
  render() {
    if (!this.hass || !this._config) return c;
    const t = St(this.hass, this._config);
    if (!t.status_entity || !h(this.hass, t.status_entity))
      return l`<ha-card><div class="card"><div class="warning"><ha-icon icon="mdi:water-alert"></ha-icon><span>${a(this.hass, "missing")}</span></div></div></ha-card>`;
    const e = h(this.hass, t.status_entity), i = h(this.hass, t.emergency_entity), n = h(this.hass, t.lock_entity), o = h(this.hass, t.winter_entity), r = h(this.hass, t.maintenance_entity), u = h(this.hass, t.automation_release_entity), d = h(this.hass, t.active_zone_entity), p = y(e, "config_entry_id"), m = Ht(d), _ = this._config.visible_actions ?? Ne, f = e?.state ?? "unavailable", $ = i?.state === "on" || n?.state === "on";
    return l`
      <ha-card>
        <div class="card ${this._config.display_mode === "compact" ? "compact" : ""}">
          <header>
            <div class="hero">
              <ha-icon .icon=${Bt(f)}></ha-icon>
              <div>
                <h2>${this._config.name ?? a(this.hass, "overview")}</h2>
                <strong>${B(e) ? Wt(this.hass, e.state) : x(this.hass, e)}</strong>
              </div>
            </div>
          </header>

          ${$ ? l`<div class="warning danger"><ha-icon icon="mdi:lock-alert-outline"></ha-icon><span>${i?.state === "on" ? a(this.hass, "emergency_stop") : a(this.hass, "safety_lock")}${y(n, "reason") ? `: ${y(n, "reason")}` : ""}</span></div>` : c}
          ${o?.state === "on" ? l`<div class="warning"><ha-icon icon="mdi:snowflake-alert"></ha-icon><span>${a(this.hass, "winter_lock")}</span></div>` : c}
          ${r?.state === "on" ? l`<div class="warning"><ha-icon icon="mdi:wrench-clock"></ha-icon><span>${a(this.hass, "maintenance_active")}</span></div>` : c}
          ${u?.state === "off" && y(u, "suspended_until") ? l`<div class="warning"><ha-icon icon="mdi:calendar-clock"></ha-icon><span>${a(this.hass, "automatic_suspended")}: ${y(u, "suspended_until")}</span></div>` : c}

          ${(this._config.visible_metrics ?? Ct).includes("active") && d ? l`
                <section>
                  <h3>${a(this.hass, "active_zone")}</h3>
                  <strong>${x(this.hass, d)}</strong>
                  ${t.dose_entity ? l`<div class="secondary">${a(this.hass, "dose")}: ${x(this.hass, h(this.hass, t.dose_entity))}</div>` : c}
                  ${m === void 0 ? c : l`<div class="secondary">${a(this.hass, "progress")}: ${Math.round(m)}%</div><progress max="100" .value=${m} aria-label=${a(this.hass, "progress")}></progress>`}
                </section>
              ` : c}

          <div class="metrics details">
            ${this.metric("pending", a(this.hass, "pending"), h(this.hass, t.pending_entity))}
            ${this.metric("next", a(this.hass, "next"), h(this.hass, t.next_entity))}
            ${this.metric("today", a(this.hass, "today"), h(this.hass, t.today_consumption_entity))}
            ${this.metric("month", a(this.hass, "month"), h(this.hass, t.month_consumption_entity))}
            ${this.metric("quality", a(this.hass, "model_quality"), h(this.hass, t.model_quality_entity))}
            ${this.metric("maintenance", a(this.hass, "maintenance_due"), h(this.hass, t.maintenance_due_entity))}
          </div>

          ${this._error ? l`<div class="error" role="alert">${this._error}</div>` : c}
          <div class="actions">
            ${_.includes("stop") ? l`<button class="danger" ?disabled=${this._busy || !B(e) || !p} @click=${() => this.call("stop", a(this.hass, "confirm_stop"))}><ha-icon icon="mdi:stop-circle-outline"></ha-icon>${a(this.hass, "stop")}</button>` : c}
            ${_.includes("emergency") ? l`<button class="danger" ?disabled=${this._busy || !p} @click=${() => this.call("emergency_stop", a(this.hass, "confirm_emergency"))}><ha-icon icon="mdi:alert-octagon-outline"></ha-icon>${a(this.hass, "emergency")}</button>` : c}
            ${_.includes("suspend") ? l`<button ?disabled=${this._busy || !p} @click=${() => this.call("suspend_automatic", a(this.hass, "confirm_suspend"), { until: new Date(Date.now() + 864e5).toISOString() })}><ha-icon icon="mdi:calendar-clock"></ha-icon>${a(this.hass, "suspend_24h")}</button>` : c}
            ${_.includes("resume") ? l`<button ?disabled=${this._busy || !p} @click=${() => this.call("resume_automatic", a(this.hass, "confirm_resume"))}><ha-icon icon="mdi:calendar-check"></ha-icon>${a(this.hass, "resume_automatic")}</button>` : c}
          </div>
        </div>
      </ha-card>
    `;
  }
};
j.styles = jt, j.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 },
  _busy: { state: !0 },
  _error: { state: !0 }
};
let st = j;
const qt = ["status", "balance", "next", "total", "recent", "quality", "calculation", "flow", "history"], Te = ["create", "start", "pause", "resume", "stop", "stop_skip", "suspend", "resume_auto", "archive", "restore"], Z = class Z extends S {
  constructor() {
    super(...arguments), this._targetMode = "duration", this._targetValue = 600, this._hardLimit = 3600, this._busy = !1;
  }
  static getConfigElement() {
    return document.createElement("irrigation-manager-zone-card-editor");
  }
  static getStubConfig() {
    return {
      type: "custom:irrigation-manager-zone-card",
      configuration_mode: "simple",
      zone: ""
    };
  }
  setConfig(t) {
    this._config = { ...t };
  }
  getCardSize() {
    return this._config?.display_mode === "compact" ? 4 : 7;
  }
  metric(t, e, i) {
    return (this._config.visible_metrics ?? qt).includes(t) ? l`<div class="metric"><span>${e}</span><strong>${x(this.hass, i)}</strong></div>` : c;
  }
  context() {
    const t = I(this.hass, this._config), e = h(this.hass, t.zone_entity), i = y(e, "config_entry_id"), n = y(e, "zone_subentry_id");
    return i && n ? { config_entry_id: i, zone_subentry_id: n } : void 0;
  }
  async perform(t, e, i) {
    if (!(i && !window.confirm(i))) {
      this._busy = !0, this._error = void 0;
      try {
        await this.hass.callService(It, t, e);
      } catch (n) {
        this._error = `${a(this.hass, "action_failed")}: ${n instanceof Error ? n.message : String(n)}`;
      } finally {
        this._busy = !1;
      }
    }
  }
  async request() {
    const t = this.context();
    if (!t) {
      this._error = a(this.hass, "configuration_error");
      return;
    }
    if (!Number.isFinite(this._targetValue) || this._targetValue <= 0) {
      this._error = a(this.hass, "invalid_target");
      return;
    }
    if (this._targetMode === "amount" && (!Number.isFinite(this._hardLimit) || this._hardLimit <= 0)) {
      this._error = a(this.hass, "hard_limit_required");
      return;
    }
    const e = this._targetMode === "duration" ? { duration: this._targetValue } : { amount: this._targetValue, hard_time_limit: this._hardLimit };
    await this.perform(fe, { ...t, ...e });
  }
  async requestAction(t) {
    const e = this.context(), i = h(this.hass, I(this.hass, this._config).request_entity), n = Q(i, e?.zone_subentry_id);
    if (!e || !n?.requestId) {
      this._error = a(this.hass, "configuration_error");
      return;
    }
    await this.perform(t, {
      config_entry_id: e.config_entry_id,
      request_id: n.requestId
    });
  }
  async stop(t = !1) {
    const e = this.context(), i = h(this.hass, I(this.hass, this._config).request_entity), n = Q(i, e?.zone_subentry_id);
    if (!e || !n) {
      this._error = a(this.hass, "configuration_error");
      return;
    }
    const o = n.executionId ? { execution_id: n.executionId } : { request_id: n.requestId };
    await this.perform(
      t ? "stop_and_skip" : "stop",
      { config_entry_id: e.config_entry_id, ...o },
      a(this.hass, t ? "confirm_stop_skip" : "confirm_stop")
    );
  }
  lockTimestamp(t) {
    const e = y(t, "occurred_at") ?? t.last_changed;
    if (!e) return;
    const i = new Date(e);
    return Number.isNaN(i.getTime()) ? e : new Intl.DateTimeFormat(this.hass.language, {
      dateStyle: "medium",
      timeStyle: "medium"
    }).format(i);
  }
  lockReason(t) {
    const e = y(t, "reason");
    if (!e) return;
    const i = [
      [" opened unexpectedly during startup", "unexpectedly_opened_during_startup"],
      [" opened unexpectedly", "unexpectedly_opened"],
      [" closed unexpectedly during irrigation", "unexpectedly_closed"]
    ];
    for (const [n, o] of i) {
      if (!e.endsWith(n)) continue;
      const r = e.slice(0, -n.length), u = h(this.hass, r)?.attributes.friendly_name;
      return `${typeof u == "string" && u ? `${u} (${r})` : r} ${a(this.hass, o)}`;
    }
    return e;
  }
  async resetSafety(t, e) {
    await this.perform(
      e?.state === "on" ? "reset_zone_safety" : "reset_installation_safety",
      e?.state === "on" ? t : { config_entry_id: t.config_entry_id },
      a(this.hass, "confirm_reset_safety")
    );
  }
  render() {
    if (!this.hass || !this._config) return c;
    const t = I(this.hass, this._config);
    if (!t.zone_entity || !h(this.hass, t.zone_entity))
      return l`<ha-card><div class="card"><div class="warning"><ha-icon icon="mdi:water-alert"></ha-icon><span>${a(this.hass, "missing")}</span></div></div></ha-card>`;
    const e = h(this.hass, t.zone_entity), i = h(this.hass, t.automation_needed_entity), n = h(this.hass, t.safety_lock_entity), o = h(this.hass, t.installation_safety_lock_entity), r = n?.state === "on" ? n : o?.state === "on" ? o : void 0, u = h(this.hass, t.quality_entity), d = h(this.hass, t.status_entity), p = h(this.hass, t.automation_release_entity), m = h(this.hass, t.archived_entity), _ = h(this.hass, t.flow_deviation_entity), f = h(this.hass, t.active_zone_entity), $ = h(this.hass, t.request_entity), g = this.context(), q = Q($, g?.zone_subentry_id), G = Ht(f), dt = this._config.visible_metrics ?? qt, v = this._config.visible_actions ?? Te, Zt = this._config.name ?? e?.attributes.friendly_name ?? a(this.hass, "zone"), ut = u?.state ?? y(e, "measurement_quality"), Ft = r && d ? { ...d, state: "safety_lock" } : d, _t = r ? this.lockReason(r) : void 0, pt = r ? this.lockTimestamp(r) : void 0, Kt = n?.state === "on" ? "zone_safety_lock" : "installation_safety_lock";
    return l`
      <ha-card>
        <div class="card ${this._config.display_mode === "compact" ? "compact" : ""}">
          <header>
            <div class="hero">
              <ha-icon .icon=${Bt(r?.state === "on" ? "safety_lock" : i?.state ?? "unknown")}></ha-icon>
              <div>
                <h2>${Zt}</h2>
                <strong>${r?.state === "on" ? a(this.hass, "locked") : i?.state === "on" ? a(this.hass, "automation_needed") : i?.state === "off" ? a(this.hass, "automation_not_needed") : x(this.hass, i)}</strong>
              </div>
            </div>
          </header>

          ${r ? l`<div class="warning danger"><ha-icon icon="mdi:lock-alert-outline"></ha-icon><span><strong>${a(this.hass, Kt)}</strong>${_t ? l`<br />${a(this.hass, "lock_reason")}: ${_t}` : c}${pt ? l`<br />${a(this.hass, "lock_occurred_at")}: ${pt}` : c}</span></div>` : c}
          ${ut === "estimated" ? l`<div class="warning"><ha-icon icon="mdi:calculator-variant-outline"></ha-icon><span>${a(this.hass, "warning_estimated")}</span></div>` : ut === "unknown" ? l`<div class="warning"><ha-icon icon="mdi:help-circle-outline"></ha-icon><span>${a(this.hass, "warning_unknown")}</span></div>` : c}
          ${p?.state === "off" && y(p, "suspended_until") ? l`<div class="warning"><ha-icon icon="mdi:calendar-clock"></ha-icon><span>${a(this.hass, "automatic_suspended")}: ${y(p, "suspended_until")}</span></div>` : c}
          ${m?.state === "on" ? l`<div class="warning"><ha-icon icon="mdi:archive-outline"></ha-icon><span>${a(this.hass, "archived")}</span></div>` : c}
          ${_ && B(_) && Math.abs(Number(_.state)) >= 20 ? l`<div class="warning"><ha-icon icon="mdi:waves-arrow-up"></ha-icon><span>${a(this.hass, "flow_warning")}: ${x(this.hass, _)}</span></div>` : c}

          ${q && f && B(f) && G !== void 0 ? l`<section><h3>${a(this.hass, "progress")}</h3><strong>${x(this.hass, f)} · ${Math.round(G)}%</strong><progress max="100" .value=${G} aria-label=${a(this.hass, "progress")}></progress></section>` : c}

          <div class="metrics">
            ${this.metric("status", a(this.hass, "status"), Ft)}
            ${this.metric("balance", a(this.hass, "water_balance"), h(this.hass, t.deficit_entity))}
            ${this.metric("balance", a(this.hass, "target"), h(this.hass, t.target_entity))}
            ${dt.includes("balance") ? this.metric("balance", a(this.hass, "explanation"), h(this.hass, t.planning_reason_entity)) : c}
            ${this.metric("next", a(this.hass, "next_window"), h(this.hass, t.next_window_entity))}
            ${this.metric("total", a(this.hass, "total"), e)}
            ${this.metric("recent", a(this.hass, "last_delivered"), h(this.hass, t.last_delivered_entity))}
            ${this.metric("recent", a(this.hass, "last_duration"), h(this.hass, t.last_duration_entity))}
            ${this.metric("quality", a(this.hass, "quality"), u)}
            ${this.metric("calculation", a(this.hass, "coverage"), h(this.hass, t.coverage_entity))}
            ${t.calculation_entity ? this.metric("calculation", a(this.hass, "explanation"), h(this.hass, t.calculation_entity)) : c}
            ${this.metric("flow", a(this.hass, "expected_flow"), h(this.hass, t.expected_flow_entity))}
            ${this.metric("flow", a(this.hass, "actual_flow"), h(this.hass, t.actual_flow_entity))}
            ${this.metric("flow", a(this.hass, "flow_deviation"), _)}
          </div>
          ${dt.includes("history") && Array.isArray(e?.attributes.recent_history) ? l`<section class="details"><h3>${a(this.hass, "history")}</h3>${e.attributes.recent_history.slice(-3).reverse().map((b) => l`<div class="secondary">${String(b.ended_at ?? b.created_at ?? "")} · ${String(b.result ?? b.status ?? "")}</div>`)}</section>` : c}

          <section class="details">
            <h3>${a(this.hass, "manual")}</h3>
            <div class="form-grid">
              <label class="field">
                <span>${a(this.hass, "target")}</span>
                <select .value=${this._targetMode} @change=${(b) => {
      this._targetMode = b.target.value;
    }}>
                  <option value="duration">${a(this.hass, "duration_mode")}</option>
                  <option value="amount">${a(this.hass, "amount_mode")}</option>
                </select>
              </label>
              <label class="field">
                <span>${this._targetMode === "duration" ? a(this.hass, "duration") : a(this.hass, "amount")}</span>
                <input type="number" min="0.001" step=${this._targetMode === "duration" ? "1" : "0.1"} .value=${String(this._targetValue)} @input=${(b) => {
      this._targetValue = Number(b.target.value);
    }} />
                <span>${this._targetMode === "duration" ? a(this.hass, "seconds") : a(this.hass, "liters")}</span>
              </label>
              ${this._targetMode === "amount" ? l`<label class="field"><span>${a(this.hass, "hard_limit")}</span><input type="number" min="0.001" max="14400" step="1" .value=${String(this._hardLimit)} @input=${(b) => {
      this._hardLimit = Number(b.target.value);
    }} /><span>${a(this.hass, "seconds")}</span></label>` : c}
            </div>
          </section>

          ${this._error ? l`<div class="error" role="alert">${this._error}</div>` : c}
          <div class="actions">
            ${v.includes("create") ? l`<button ?disabled=${this._busy || r?.state === "on" || !g} @click=${this.request}><ha-icon icon="mdi:playlist-plus"></ha-icon>${a(this.hass, "create")}</button>` : c}
            ${v.includes("start") ? l`<button class="primary" ?disabled=${this._busy || r?.state === "on" || !g} @click=${this.request}><ha-icon icon="mdi:play"></ha-icon>${a(this.hass, "start")}</button>` : c}
            ${v.includes("pause") ? l`<button ?disabled=${this._busy || !q?.requestId} @click=${() => this.requestAction("pause_request")}><ha-icon icon="mdi:pause"></ha-icon>${a(this.hass, "pause")}</button>` : c}
            ${v.includes("resume") ? l`<button ?disabled=${this._busy || !q?.requestId} @click=${() => this.requestAction("resume_request")}><ha-icon icon="mdi:play-pause"></ha-icon>${a(this.hass, "resume")}</button>` : c}
            ${v.includes("stop") ? l`<button class="danger" ?disabled=${this._busy || !q} @click=${() => this.stop()}><ha-icon icon="mdi:stop-circle-outline"></ha-icon>${a(this.hass, "stop")}</button>` : c}
            ${v.includes("stop_skip") ? l`<button class="danger" ?disabled=${this._busy || !q} @click=${() => this.stop(!0)}><ha-icon icon="mdi:skip-next-circle-outline"></ha-icon>${a(this.hass, "stop_skip")}</button>` : c}
            ${v.includes("suspend") ? l`<button ?disabled=${this._busy || !g || m?.state === "on"} @click=${() => g && this.perform("suspend_automatic", { ...g, until: new Date(Date.now() + 864e5).toISOString() })}><ha-icon icon="mdi:calendar-clock"></ha-icon>${a(this.hass, "suspend_24h")}</button>` : c}
            ${v.includes("resume_auto") ? l`<button ?disabled=${this._busy || !g} @click=${() => g && this.perform("resume_automatic", g)}><ha-icon icon="mdi:calendar-check"></ha-icon>${a(this.hass, "resume_automatic")}</button>` : c}
            ${r ? l`<button data-testid="reset-safety" class="danger" ?disabled=${this._busy || !g} @click=${() => g && this.resetSafety(g, n)}><ha-icon icon="mdi:lock-open-alert-outline"></ha-icon>${a(this.hass, "reset_safety")}</button>` : c}
            ${v.includes("archive") ? l`<button ?disabled=${this._busy || !g || m?.state === "on"} @click=${() => g && this.perform("archive_zone", g, a(this.hass, "confirm_archive"))}><ha-icon icon="mdi:archive-arrow-down-outline"></ha-icon>${a(this.hass, "archive")}</button>` : c}
            ${v.includes("restore") ? l`<button ?disabled=${this._busy || !g || m?.state !== "on"} @click=${() => g && this.perform("restore_zone", g)}><ha-icon icon="mdi:archive-arrow-up-outline"></ha-icon>${a(this.hass, "restore")}</button>` : c}
          </div>
        </div>
      </ha-card>
    `;
  }
};
Z.styles = jt, Z.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 },
  _targetMode: { state: !0 },
  _targetValue: { state: !0 },
  _hardLimit: { state: !0 },
  _busy: { state: !0 },
  _error: { state: !0 }
};
let nt = Z;
const Pe = [
  ["irrigation-manager-overview-card", st],
  ["irrigation-manager-zone-card", nt],
  ["irrigation-manager-overview-card-editor", Ce],
  ["irrigation-manager-zone-card-editor", qe]
];
for (const [s, t] of Pe)
  customElements.get(s) || customElements.define(s, t);
window.customCards = window.customCards ?? [];
for (const s of [
  {
    type: "irrigation-manager-overview-card",
    name: "Irrigation Manager Overview",
    description: "Select an installation for automatic status, metrics and safety actions.",
    preview: !0
  },
  {
    type: "irrigation-manager-zone-card",
    name: "Irrigation Manager Zone",
    description: "Select a zone for automatic water balance, planning and native controls.",
    preview: !0
  }
])
  window.customCards.some((t) => t.type === s.type) || window.customCards.push(s);
