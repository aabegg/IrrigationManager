const I = globalThis, st = I.ShadowRoot && (I.ShadyCSS === void 0 || I.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype, nt = /* @__PURE__ */ Symbol(), dt = /* @__PURE__ */ new WeakMap();
let zt = class {
  constructor(t, e, i) {
    if (this._$cssResult$ = !0, i !== nt) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
    this.cssText = t, this.t = e;
  }
  get styleSheet() {
    let t = this.o;
    const e = this.t;
    if (st && t === void 0) {
      const i = e !== void 0 && e.length === 1;
      i && (t = dt.get(e)), t === void 0 && ((this.o = t = new CSSStyleSheet()).replaceSync(this.cssText), i && dt.set(e, t));
    }
    return t;
  }
  toString() {
    return this.cssText;
  }
};
const Vt = (s) => new zt(typeof s == "string" ? s : s + "", void 0, nt), Mt = (s, ...t) => {
  const e = s.length === 1 ? s[0] : t.reduce((i, n, o) => i + ((r) => {
    if (r._$cssResult$ === !0) return r.cssText;
    if (typeof r == "number") return r;
    throw Error("Value passed to 'css' function must be a 'css' function result: " + r + ". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.");
  })(n) + s[o + 1], s[0]);
  return new zt(e, s, nt);
}, Wt = (s, t) => {
  if (st) s.adoptedStyleSheets = t.map((e) => e instanceof CSSStyleSheet ? e : e.styleSheet);
  else for (const e of t) {
    const i = document.createElement("style"), n = I.litNonce;
    n !== void 0 && i.setAttribute("nonce", n), i.textContent = e.cssText, s.appendChild(i);
  }
}, ut = st ? (s) => s : (s) => s instanceof CSSStyleSheet ? ((t) => {
  let e = "";
  for (const i of t.cssRules) e += i.cssText;
  return Vt(e);
})(s) : s;
const { is: jt, defineProperty: Ft, getOwnPropertyDescriptor: Zt, getOwnPropertyNames: Kt, getOwnPropertySymbols: Gt, getPrototypeOf: Jt } = Object, F = globalThis, pt = F.trustedTypes, Qt = pt ? pt.emptyScript : "", Yt = F.reactiveElementPolyfillSupport, N = (s, t) => s, J = { toAttribute(s, t) {
  switch (t) {
    case Boolean:
      s = s ? Qt : null;
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
} }, Ct = (s, t) => !jt(s, t), _t = { attribute: !0, type: String, converter: J, reflect: !1, useDefault: !1, hasChanged: Ct };
Symbol.metadata ??= /* @__PURE__ */ Symbol("metadata"), F.litPropertyMetadata ??= /* @__PURE__ */ new WeakMap();
let z = class extends HTMLElement {
  static addInitializer(t) {
    this._$Ei(), (this.l ??= []).push(t);
  }
  static get observedAttributes() {
    return this.finalize(), this._$Eh && [...this._$Eh.keys()];
  }
  static createProperty(t, e = _t) {
    if (e.state && (e.attribute = !1), this._$Ei(), this.prototype.hasOwnProperty(t) && ((e = Object.create(e)).wrapped = !0), this.elementProperties.set(t, e), !e.noAccessor) {
      const i = /* @__PURE__ */ Symbol(), n = this.getPropertyDescriptor(t, i, e);
      n !== void 0 && Ft(this.prototype, t, n);
    }
  }
  static getPropertyDescriptor(t, e, i) {
    const { get: n, set: o } = Zt(this.prototype, t) ?? { get() {
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
    return this.elementProperties.get(t) ?? _t;
  }
  static _$Ei() {
    if (this.hasOwnProperty(N("elementProperties"))) return;
    const t = Jt(this);
    t.finalize(), t.l !== void 0 && (this.l = [...t.l]), this.elementProperties = new Map(t.elementProperties);
  }
  static finalize() {
    if (this.hasOwnProperty(N("finalized"))) return;
    if (this.finalized = !0, this._$Ei(), this.hasOwnProperty(N("properties"))) {
      const e = this.properties, i = [...Kt(e), ...Gt(e)];
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
      for (const n of i) e.unshift(ut(n));
    } else t !== void 0 && e.push(ut(t));
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
    return Wt(t, this.constructor.elementStyles), t;
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
      const o = (i.converter?.toAttribute !== void 0 ? i.converter : J).toAttribute(e, i.type);
      this._$Em = t, o == null ? this.removeAttribute(n) : this.setAttribute(n, o), this._$Em = null;
    }
  }
  _$AK(t, e) {
    const i = this.constructor, n = i._$Eh.get(t);
    if (n !== void 0 && this._$Em !== n) {
      const o = i.getPropertyOptions(n), r = typeof o.converter == "function" ? { fromAttribute: o.converter } : o.converter?.fromAttribute !== void 0 ? o.converter : J;
      this._$Em = n;
      const u = r.fromAttribute(e, o.type);
      this[n] = u ?? this._$Ej?.get(n) ?? u, this._$Em = null;
    }
  }
  requestUpdate(t, e, i, n = !1, o) {
    if (t !== void 0) {
      const r = this.constructor;
      if (n === !1 && (o = this[t]), i ??= r.getPropertyOptions(t), !((i.hasChanged ?? Ct)(o, e) || i.useDefault && i.reflect && o === this._$Ej?.get(t) && !this.hasAttribute(r._$Eu(t, i)))) return;
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
z.elementStyles = [], z.shadowRootOptions = { mode: "open" }, z[N("elementProperties")] = /* @__PURE__ */ new Map(), z[N("finalized")] = /* @__PURE__ */ new Map(), Yt?.({ ReactiveElement: z }), (F.reactiveElementVersions ??= []).push("2.1.2");
const at = globalThis, mt = (s) => s, L = at.trustedTypes, gt = L ? L.createPolicy("lit-html", { createHTML: (s) => s }) : void 0, qt = "$lit$", w = `lit$${Math.random().toFixed(9).slice(2)}$`, Nt = "?" + w, Xt = `<${Nt}>`, E = document, P = () => E.createComment(""), T = (s) => s === null || typeof s != "object" && typeof s != "function", ot = Array.isArray, te = (s) => ot(s) || typeof s?.[Symbol.iterator] == "function", K = `[\x20\t\n\f\r]`, q = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g, ft = /-->/g, yt = />/g, x = RegExp(`>|${K}(?:([^\\s"'>=/]+)(${K}*=${K}*(?:[^\x20\t\n\f\r"'\`<>=]|("|')|))|$)`, "g"), $t = /'/g, vt = /"/g, Pt = /^(?:script|style|textarea|title)$/i, ee = (s) => (t, ...e) => ({ _$litType$: s, strings: t, values: e }), l = ee(1), M = /* @__PURE__ */ Symbol.for("lit-noChange"), c = /* @__PURE__ */ Symbol.for("lit-nothing"), bt = /* @__PURE__ */ new WeakMap(), k = E.createTreeWalker(E, 129);
function Tt(s, t) {
  if (!ot(s) || !s.hasOwnProperty("raw")) throw Error("invalid template strings array");
  return gt !== void 0 ? gt.createHTML(t) : t;
}
const ie = (s, t) => {
  const e = s.length - 1, i = [];
  let n, o = t === 2 ? "<svg>" : t === 3 ? "<math>" : "", r = q;
  for (let u = 0; u < e; u++) {
    const h = s[u];
    let _, g, p = -1, m = 0;
    for (; m < h.length && (r.lastIndex = m, g = r.exec(h), g !== null); ) m = r.lastIndex, r === q ? g[1] === "!--" ? r = ft : g[1] !== void 0 ? r = yt : g[2] !== void 0 ? (Pt.test(g[2]) && (n = RegExp("</" + g[2], "g")), r = x) : g[3] !== void 0 && (r = x) : r === x ? g[0] === ">" ? (r = n ?? q, p = -1) : g[1] === void 0 ? p = -2 : (p = r.lastIndex - g[2].length, _ = g[1], r = g[3] === void 0 ? x : g[3] === '"' ? vt : $t) : r === vt || r === $t ? r = x : r === ft || r === yt ? r = q : (r = x, n = void 0);
    const f = r === x && s[u + 1].startsWith("/>") ? " " : "";
    o += r === q ? h + Xt : p >= 0 ? (i.push(_), h.slice(0, p) + qt + h.slice(p) + w + f) : h + w + (p === -2 ? u : f);
  }
  return [Tt(s, o + (s[e] || "<?>") + (t === 2 ? "</svg>" : t === 3 ? "</math>" : "")), i];
};
class O {
  constructor({ strings: t, _$litType$: e }, i) {
    let n;
    this.parts = [];
    let o = 0, r = 0;
    const u = t.length - 1, h = this.parts, [_, g] = ie(t, e);
    if (this.el = O.createElement(_, i), k.currentNode = this.el.content, e === 2 || e === 3) {
      const p = this.el.content.firstChild;
      p.replaceWith(...p.childNodes);
    }
    for (; (n = k.nextNode()) !== null && h.length < u; ) {
      if (n.nodeType === 1) {
        if (n.hasAttributes()) for (const p of n.getAttributeNames()) if (p.endsWith(qt)) {
          const m = g[r++], f = n.getAttribute(p).split(w), b = /([.?@])?(.*)/.exec(m);
          h.push({ type: 1, index: o, name: b[2], strings: f, ctor: b[1] === "." ? ne : b[1] === "?" ? ae : b[1] === "@" ? oe : Z }), n.removeAttribute(p);
        } else p.startsWith(w) && (h.push({ type: 6, index: o }), n.removeAttribute(p));
        if (Pt.test(n.tagName)) {
          const p = n.textContent.split(w), m = p.length - 1;
          if (m > 0) {
            n.textContent = L ? L.emptyScript : "";
            for (let f = 0; f < m; f++) n.append(p[f], P()), k.nextNode(), h.push({ type: 2, index: ++o });
            n.append(p[m], P());
          }
        }
      } else if (n.nodeType === 8) if (n.data === Nt) h.push({ type: 2, index: o });
      else {
        let p = -1;
        for (; (p = n.data.indexOf(w, p + 1)) !== -1; ) h.push({ type: 7, index: o }), p += w.length - 1;
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
  const o = T(t) ? void 0 : t._$litDirective$;
  return n?.constructor !== o && (n?._$AO?.(!1), o === void 0 ? n = void 0 : (n = new o(s), n._$AT(s, e, i)), i !== void 0 ? (e._$Co ??= [])[i] = n : e._$Cl = n), n !== void 0 && (t = C(s, n._$AS(s, t.values), n, i)), t;
}
class se {
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
    let o = k.nextNode(), r = 0, u = 0, h = i[0];
    for (; h !== void 0; ) {
      if (r === h.index) {
        let _;
        h.type === 2 ? _ = new U(o, o.nextSibling, this, t) : h.type === 1 ? _ = new h.ctor(o, h.name, h.strings, this, t) : h.type === 6 && (_ = new re(o, this, t)), this._$AV.push(_), h = i[++u];
      }
      r !== h?.index && (o = k.nextNode(), r++);
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
    t = C(this, t, e), T(t) ? t === c || t == null || t === "" ? (this._$AH !== c && this._$AR(), this._$AH = c) : t !== this._$AH && t !== M && this._(t) : t._$litType$ !== void 0 ? this.$(t) : t.nodeType !== void 0 ? this.T(t) : te(t) ? this.k(t) : this._(t);
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
    const { values: e, _$litType$: i } = t, n = typeof i == "number" ? this._$AC(t) : (i.el === void 0 && (i.el = O.createElement(Tt(i.h, i.h[0]), this.options)), i);
    if (this._$AH?._$AD === n) this._$AH.p(e);
    else {
      const o = new se(n, this), r = o.u(this.options);
      o.p(e), this.T(r), this._$AH = o;
    }
  }
  _$AC(t) {
    let e = bt.get(t.strings);
    return e === void 0 && bt.set(t.strings, e = new O(t)), e;
  }
  k(t) {
    ot(this._$AH) || (this._$AH = [], this._$AR());
    const e = this._$AH;
    let i, n = 0;
    for (const o of t) n === e.length ? e.push(i = new U(this.O(P()), this.O(P()), this, this.options)) : i = e[n], i._$AI(o), n++;
    n < e.length && (this._$AR(i && i._$AB.nextSibling, n), e.length = n);
  }
  _$AR(t = this._$AA.nextSibling, e) {
    for (this._$AP?.(!1, !0, e); t !== this._$AB; ) {
      const i = mt(t).nextSibling;
      mt(t).remove(), t = i;
    }
  }
  setConnected(t) {
    this._$AM === void 0 && (this._$Cv = t, this._$AP?.(t));
  }
}
class Z {
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
    if (o === void 0) t = C(this, t, e, 0), r = !T(t) || t !== this._$AH && t !== M, r && (this._$AH = t);
    else {
      const u = t;
      let h, _;
      for (t = o[0], h = 0; h < o.length - 1; h++) _ = C(this, u[i + h], e, h), _ === M && (_ = this._$AH[h]), r ||= !T(_) || _ !== this._$AH[h], _ === c ? t = c : t !== c && (t += (_ ?? "") + o[h + 1]), this._$AH[h] = _;
    }
    r && !n && this.j(t);
  }
  j(t) {
    t === c ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, t ?? "");
  }
}
class ne extends Z {
  constructor() {
    super(...arguments), this.type = 3;
  }
  j(t) {
    this.element[this.name] = t === c ? void 0 : t;
  }
}
class ae extends Z {
  constructor() {
    super(...arguments), this.type = 4;
  }
  j(t) {
    this.element.toggleAttribute(this.name, !!t && t !== c);
  }
}
class oe extends Z {
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
class re {
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
const ce = at.litHtmlPolyfillSupport;
ce?.(O, U), (at.litHtmlVersions ??= []).push("3.3.3");
const le = (s, t, e) => {
  const i = e?.renderBefore ?? t;
  let n = i._$litPart$;
  if (n === void 0) {
    const o = e?.renderBefore ?? null;
    i._$litPart$ = n = new U(t.insertBefore(P(), o), o, void 0, e ?? {});
  }
  return n._$AI(s), n;
};
const rt = globalThis;
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
    this.hasUpdated || (this.renderOptions.isConnected = this.isConnected), super.update(t), this._$Do = le(e, this.renderRoot, this.renderOptions);
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
S._$litElement$ = !0, S.finalized = !0, rt.litElementHydrateSupport?.({ LitElement: S });
const he = rt.litElementPolyfillSupport;
he?.({ LitElement: S });
(rt.litElementVersions ??= []).push("4.2.2");
const Ot = "irrigation_manager", de = "create_manual", ue = /* @__PURE__ */ new Set(["unknown", "unavailable"]), pe = {
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
}, _e = {
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
}, me = {
  active_zone: "active_zone_entity",
  dose: "request_entity"
};
function R(s, t) {
  const e = s?.attributes[t];
  return !e || typeof e != "object" || Array.isArray(e) ? {} : Object.fromEntries(
    Object.entries(e).filter(
      (i) => typeof i[1] == "string" && i[1].includes(".")
    )
  );
}
function Q(s, t, e) {
  const i = { ...s };
  for (const [n, o] of Object.entries(e)) {
    const u = s[o] || t[n];
    u && Object.assign(i, { [o]: u });
  }
  return i;
}
function wt(s, t) {
  if (!t.configuration_mode && !t.installation && t.status_entity) return t;
  const e = t.installation ? Rt(s, "installation", t.installation) : d(s, t.status_entity);
  return Q(t, R(e, "card_entities"), pe);
}
function D(s, t) {
  if (!t.configuration_mode && !t.zone && t.zone_entity) return t;
  const e = t.zone ? Rt(s, "zone", t.zone) : d(s, t.zone_entity);
  let i = Q(t, R(e, "card_entities"), _e);
  return i = Q(
    i,
    R(e, "installation_card_entities"),
    me
  ), !i.zone_entity && e && (i.zone_entity = e.entity_id), i;
}
function Rt(s, t, e) {
  return Object.values(s.states).find((i) => Y(i, t) === e);
}
function Y(s, t) {
  const e = s.attributes.config_entry_id;
  if (typeof e != "string") return;
  if (t === "installation")
    return R(s, "card_entities").status === s.entity_id ? e : void 0;
  const i = s.attributes.zone_subentry_id;
  return typeof i == "string" && Object.keys(R(s, "card_entities")).length > 0 ? `${e}:${i}` : void 0;
}
function ct(s, t) {
  return s.configuration_mode ? s.configuration_mode : t.some((e) => !!s[e]) ? "expert" : "simple";
}
function ge(s, t) {
  return Object.values(s.states).filter((e) => Y(e, t) !== void 0).map((e) => ({
    value: Y(e, t),
    label: typeof e.attributes.card_name == "string" && e.attributes.card_name || e.attributes.friendly_name || e.entity_id
  })).sort((e, i) => e.label.localeCompare(i.label, s.language));
}
function d(s, t) {
  return t ? s.states[t] : void 0;
}
function H(s) {
  return !!(s && !ue.has(s.state));
}
function y(s, t) {
  const e = s?.attributes[t];
  return typeof e == "string" && e ? e : void 0;
}
function At(s, t) {
  const e = s?.attributes[t];
  return typeof e == "number" && Number.isFinite(e) ? e : void 0;
}
function G(s, t) {
  if (!t || y(s, "zone_subentry_id") !== t)
    return;
  const e = y(s, "request_id"), i = y(s, "execution_id");
  return e || i ? { requestId: e, executionId: i } : void 0;
}
function Ut(s) {
  const t = At(s, "target_value"), e = At(s, "remaining_value");
  if (!(t === void 0 || e === void 0 || t <= 0))
    return Math.max(0, Math.min(100, (t - e) / t * 100));
}
function Dt(s) {
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
function fe(s, t) {
  s.dispatchEvent(
    new CustomEvent("config-changed", {
      detail: { config: t },
      bubbles: !0,
      composed: !0
    })
  );
}
const It = {
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
  return It[e][t];
}
function Lt(s, t) {
  return t in It.en ? a(s, t) : t.replaceAll("_", " ");
}
function A(s, t) {
  if (!t) return a(s, "missing");
  if (t.state === "unavailable") return a(s, "unavailable");
  if (t.state === "unknown" || t.state === "") return a(s, "unknown");
  if (s.formatEntityState) return s.formatEntityState(t);
  const e = t.attributes.unit_of_measurement;
  return `${Lt(s, t.state)}${e ? ` ${e}` : ""}`;
}
const Ht = Mt`
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
`, ye = Mt`
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
`, X = [
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
], tt = [
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
], xt = X.map(([s]) => s), kt = tt.map(([s]) => s), $e = {
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
}, ve = ["active", "pending", "next", "today", "month", "quality", "maintenance"], be = ["stop", "emergency", "suspend", "resume"], we = ["status", "balance", "next", "total", "recent", "quality", "calculation", "flow", "history"], Ae = ["create", "start", "pause", "resume", "stop", "stop_skip", "suspend", "resume_auto", "archive", "restore"], V = class V extends S {
  setConfig(t) {
    this._config = { ...t };
  }
  updateValue(t, e) {
    const i = { ...this._config, [t]: e || void 0 };
    e || delete i[t], this._config = i, fe(this, i);
  }
  entitySelector(t, e, i) {
    const n = this.hass.language.toLowerCase().startsWith("de") ? $e[e] ?? e : e;
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
    const e = ct(this._config, t);
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
    const n = ge(this.hass, e);
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
V.styles = ye, V.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 }
};
let B = V;
class xe extends B {
  render() {
    if (!this.hass || !this._config) return c;
    const t = ct(this._config, xt);
    return l`
      <div class="editor">
        <section>${this.configurationMode(xt)}</section>
        ${t === "simple" ? l`<section>${this.anchorSelector("installation", "installation")}</section>` : l`
              <section>
                <h3>${a(this.hass, "required_entity")}</h3>
                ${this.entitySelector("status_entity", X[0][1], !0)}
              </section>
              <section>
                <h3>${a(this.hass, "optional_entities")}</h3>
                ${X.slice(1).map(([e, i]) => this.entitySelector(e, i, !1))}
              </section>
            `}
        <section>${this.displayMode()}</section>
        <section>
          <h3>${a(this.hass, "metrics")}</h3>
          ${this.choices("visible_metrics", ve)}
        </section>
        <section>
          <h3>${a(this.hass, "actions")}</h3>
          ${this.choices("visible_actions", be)}
        </section>
      </div>
    `;
  }
}
class ke extends B {
  render() {
    if (!this.hass || !this._config) return c;
    const t = ct(this._config, kt);
    return l`
      <div class="editor">
        <section>${this.configurationMode(kt)}</section>
        ${t === "simple" ? l`<section>${this.anchorSelector("zone", "zone")}</section>` : l`
              <section>
                <h3>${a(this.hass, "required_entity")}</h3>
                ${this.entitySelector("zone_entity", tt[0][1], !0)}
              </section>
              <section>
                <h3>${a(this.hass, "optional_entities")}</h3>
                ${tt.slice(1).map(([e, i]) => this.entitySelector(e, i, !1))}
              </section>
            `}
        <section>${this.displayMode()}</section>
        <section>
          <h3>${a(this.hass, "metrics")}</h3>
          ${this.choices("visible_metrics", we)}
        </section>
        <section>
          <h3>${a(this.hass, "actions")}</h3>
          ${this.choices("visible_actions", Ae)}
        </section>
      </div>
    `;
  }
}
const St = ["active", "pending", "next", "today", "month", "quality", "maintenance"], Se = ["stop", "emergency", "suspend", "resume"], W = class W extends S {
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
    return (this._config.visible_metrics ?? St).includes(t) ? l`<div class="metric"><span>${e}</span><strong>${A(this.hass, i)}</strong></div>` : c;
  }
  async call(t, e, i = {}) {
    if (!window.confirm(e)) return;
    const n = wt(this.hass, this._config), o = d(this.hass, n.status_entity), r = y(o, "config_entry_id");
    if (!r) {
      this._error = a(this.hass, "configuration_error");
      return;
    }
    this._busy = !0, this._error = void 0;
    try {
      await this.hass.callService(Ot, t, { config_entry_id: r, ...i });
    } catch (u) {
      this._error = `${a(this.hass, "action_failed")}: ${u instanceof Error ? u.message : String(u)}`;
    } finally {
      this._busy = !1;
    }
  }
  render() {
    if (!this.hass || !this._config) return c;
    const t = wt(this.hass, this._config);
    if (!t.status_entity || !d(this.hass, t.status_entity))
      return l`<ha-card><div class="card"><div class="warning"><ha-icon icon="mdi:water-alert"></ha-icon><span>${a(this.hass, "missing")}</span></div></div></ha-card>`;
    const e = d(this.hass, t.status_entity), i = d(this.hass, t.emergency_entity), n = d(this.hass, t.lock_entity), o = d(this.hass, t.winter_entity), r = d(this.hass, t.maintenance_entity), u = d(this.hass, t.automation_release_entity), h = d(this.hass, t.active_zone_entity), _ = y(e, "config_entry_id"), g = Ut(h), p = this._config.visible_actions ?? Se, m = e?.state ?? "unavailable", f = i?.state === "on" || n?.state === "on";
    return l`
      <ha-card>
        <div class="card ${this._config.display_mode === "compact" ? "compact" : ""}">
          <header>
            <div class="hero">
              <ha-icon .icon=${Dt(m)}></ha-icon>
              <div>
                <h2>${this._config.name ?? a(this.hass, "overview")}</h2>
                <strong>${H(e) ? Lt(this.hass, e.state) : A(this.hass, e)}</strong>
              </div>
            </div>
          </header>

          ${f ? l`<div class="warning danger"><ha-icon icon="mdi:lock-alert-outline"></ha-icon><span>${i?.state === "on" ? a(this.hass, "emergency_stop") : a(this.hass, "safety_lock")}${y(n, "reason") ? `: ${y(n, "reason")}` : ""}</span></div>` : c}
          ${o?.state === "on" ? l`<div class="warning"><ha-icon icon="mdi:snowflake-alert"></ha-icon><span>${a(this.hass, "winter_lock")}</span></div>` : c}
          ${r?.state === "on" ? l`<div class="warning"><ha-icon icon="mdi:wrench-clock"></ha-icon><span>${a(this.hass, "maintenance_active")}</span></div>` : c}
          ${u?.state === "off" && y(u, "suspended_until") ? l`<div class="warning"><ha-icon icon="mdi:calendar-clock"></ha-icon><span>${a(this.hass, "automatic_suspended")}: ${y(u, "suspended_until")}</span></div>` : c}

          ${(this._config.visible_metrics ?? St).includes("active") && h ? l`
                <section>
                  <h3>${a(this.hass, "active_zone")}</h3>
                  <strong>${A(this.hass, h)}</strong>
                  ${t.dose_entity ? l`<div class="secondary">${a(this.hass, "dose")}: ${A(this.hass, d(this.hass, t.dose_entity))}</div>` : c}
                  ${g === void 0 ? c : l`<div class="secondary">${a(this.hass, "progress")}: ${Math.round(g)}%</div><progress max="100" .value=${g} aria-label=${a(this.hass, "progress")}></progress>`}
                </section>
              ` : c}

          <div class="metrics details">
            ${this.metric("pending", a(this.hass, "pending"), d(this.hass, t.pending_entity))}
            ${this.metric("next", a(this.hass, "next"), d(this.hass, t.next_entity))}
            ${this.metric("today", a(this.hass, "today"), d(this.hass, t.today_consumption_entity))}
            ${this.metric("month", a(this.hass, "month"), d(this.hass, t.month_consumption_entity))}
            ${this.metric("quality", a(this.hass, "model_quality"), d(this.hass, t.model_quality_entity))}
            ${this.metric("maintenance", a(this.hass, "maintenance_due"), d(this.hass, t.maintenance_due_entity))}
          </div>

          ${this._error ? l`<div class="error" role="alert">${this._error}</div>` : c}
          <div class="actions">
            ${p.includes("stop") ? l`<button class="danger" ?disabled=${this._busy || !H(e) || !_} @click=${() => this.call("stop", a(this.hass, "confirm_stop"))}><ha-icon icon="mdi:stop-circle-outline"></ha-icon>${a(this.hass, "stop")}</button>` : c}
            ${p.includes("emergency") ? l`<button class="danger" ?disabled=${this._busy || !_} @click=${() => this.call("emergency_stop", a(this.hass, "confirm_emergency"))}><ha-icon icon="mdi:alert-octagon-outline"></ha-icon>${a(this.hass, "emergency")}</button>` : c}
            ${p.includes("suspend") ? l`<button ?disabled=${this._busy || !_} @click=${() => this.call("suspend_automatic", a(this.hass, "confirm_suspend"), { until: new Date(Date.now() + 864e5).toISOString() })}><ha-icon icon="mdi:calendar-clock"></ha-icon>${a(this.hass, "suspend_24h")}</button>` : c}
            ${p.includes("resume") ? l`<button ?disabled=${this._busy || !_} @click=${() => this.call("resume_automatic", a(this.hass, "confirm_resume"))}><ha-icon icon="mdi:calendar-check"></ha-icon>${a(this.hass, "resume_automatic")}</button>` : c}
          </div>
        </div>
      </ha-card>
    `;
  }
};
W.styles = Ht, W.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 },
  _busy: { state: !0 },
  _error: { state: !0 }
};
let et = W;
const Et = ["status", "balance", "next", "total", "recent", "quality", "calculation", "flow", "history"], Ee = ["create", "start", "pause", "resume", "stop", "stop_skip", "suspend", "resume_auto", "archive", "restore"], j = class j extends S {
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
    return (this._config.visible_metrics ?? Et).includes(t) ? l`<div class="metric"><span>${e}</span><strong>${A(this.hass, i)}</strong></div>` : c;
  }
  context() {
    const t = D(this.hass, this._config), e = d(this.hass, t.zone_entity), i = y(e, "config_entry_id"), n = y(e, "zone_subentry_id");
    return i && n ? { config_entry_id: i, zone_subentry_id: n } : void 0;
  }
  async perform(t, e, i) {
    if (!(i && !window.confirm(i))) {
      this._busy = !0, this._error = void 0;
      try {
        await this.hass.callService(Ot, t, e);
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
    await this.perform(de, { ...t, ...e });
  }
  async requestAction(t) {
    const e = this.context(), i = d(this.hass, D(this.hass, this._config).request_entity), n = G(i, e?.zone_subentry_id);
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
    const e = this.context(), i = d(this.hass, D(this.hass, this._config).request_entity), n = G(i, e?.zone_subentry_id);
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
  render() {
    if (!this.hass || !this._config) return c;
    const t = D(this.hass, this._config);
    if (!t.zone_entity || !d(this.hass, t.zone_entity))
      return l`<ha-card><div class="card"><div class="warning"><ha-icon icon="mdi:water-alert"></ha-icon><span>${a(this.hass, "missing")}</span></div></div></ha-card>`;
    const e = d(this.hass, t.zone_entity), i = d(this.hass, t.automation_needed_entity), n = d(this.hass, t.safety_lock_entity), o = d(this.hass, t.quality_entity), r = d(this.hass, t.status_entity), u = d(this.hass, t.automation_release_entity), h = d(this.hass, t.archived_entity), _ = d(this.hass, t.flow_deviation_entity), g = d(this.hass, t.active_zone_entity), p = d(this.hass, t.request_entity), m = this.context(), f = G(p, m?.zone_subentry_id), b = Ut(g), lt = this._config.visible_metrics ?? Et, $ = this._config.visible_actions ?? Ee, Bt = this._config.name ?? e?.attributes.friendly_name ?? a(this.hass, "zone"), ht = o?.state ?? y(e, "measurement_quality");
    return l`
      <ha-card>
        <div class="card ${this._config.display_mode === "compact" ? "compact" : ""}">
          <header>
            <div class="hero">
              <ha-icon .icon=${Dt(n?.state === "on" ? "safety_lock" : i?.state ?? "unknown")}></ha-icon>
              <div>
                <h2>${Bt}</h2>
                <strong>${n?.state === "on" ? a(this.hass, "locked") : i?.state === "on" ? a(this.hass, "automation_needed") : i?.state === "off" ? a(this.hass, "automation_not_needed") : A(this.hass, i)}</strong>
              </div>
            </div>
          </header>

          ${n?.state === "on" ? l`<div class="warning danger"><ha-icon icon="mdi:lock-alert-outline"></ha-icon><span>${a(this.hass, "safety_lock")}${y(n, "reason") ? `: ${y(n, "reason")}` : ""}</span></div>` : c}
          ${ht === "estimated" ? l`<div class="warning"><ha-icon icon="mdi:calculator-variant-outline"></ha-icon><span>${a(this.hass, "warning_estimated")}</span></div>` : ht === "unknown" ? l`<div class="warning"><ha-icon icon="mdi:help-circle-outline"></ha-icon><span>${a(this.hass, "warning_unknown")}</span></div>` : c}
          ${u?.state === "off" && y(u, "suspended_until") ? l`<div class="warning"><ha-icon icon="mdi:calendar-clock"></ha-icon><span>${a(this.hass, "automatic_suspended")}: ${y(u, "suspended_until")}</span></div>` : c}
          ${h?.state === "on" ? l`<div class="warning"><ha-icon icon="mdi:archive-outline"></ha-icon><span>${a(this.hass, "archived")}</span></div>` : c}
          ${_ && H(_) && Math.abs(Number(_.state)) >= 20 ? l`<div class="warning"><ha-icon icon="mdi:waves-arrow-up"></ha-icon><span>${a(this.hass, "flow_warning")}: ${A(this.hass, _)}</span></div>` : c}

          ${f && g && H(g) && b !== void 0 ? l`<section><h3>${a(this.hass, "progress")}</h3><strong>${A(this.hass, g)} · ${Math.round(b)}%</strong><progress max="100" .value=${b} aria-label=${a(this.hass, "progress")}></progress></section>` : c}

          <div class="metrics">
            ${this.metric("status", a(this.hass, "status"), r)}
            ${this.metric("balance", a(this.hass, "water_balance"), d(this.hass, t.deficit_entity))}
            ${this.metric("balance", a(this.hass, "target"), d(this.hass, t.target_entity))}
            ${lt.includes("balance") ? this.metric("balance", a(this.hass, "explanation"), d(this.hass, t.planning_reason_entity)) : c}
            ${this.metric("next", a(this.hass, "next_window"), d(this.hass, t.next_window_entity))}
            ${this.metric("total", a(this.hass, "total"), e)}
            ${this.metric("recent", a(this.hass, "last_delivered"), d(this.hass, t.last_delivered_entity))}
            ${this.metric("recent", a(this.hass, "last_duration"), d(this.hass, t.last_duration_entity))}
            ${this.metric("quality", a(this.hass, "quality"), o)}
            ${this.metric("calculation", a(this.hass, "coverage"), d(this.hass, t.coverage_entity))}
            ${t.calculation_entity ? this.metric("calculation", a(this.hass, "explanation"), d(this.hass, t.calculation_entity)) : c}
            ${this.metric("flow", a(this.hass, "expected_flow"), d(this.hass, t.expected_flow_entity))}
            ${this.metric("flow", a(this.hass, "actual_flow"), d(this.hass, t.actual_flow_entity))}
            ${this.metric("flow", a(this.hass, "flow_deviation"), _)}
          </div>
          ${lt.includes("history") && Array.isArray(e?.attributes.recent_history) ? l`<section class="details"><h3>${a(this.hass, "history")}</h3>${e.attributes.recent_history.slice(-3).reverse().map((v) => l`<div class="secondary">${String(v.ended_at ?? v.created_at ?? "")} · ${String(v.result ?? v.status ?? "")}</div>`)}</section>` : c}

          <section class="details">
            <h3>${a(this.hass, "manual")}</h3>
            <div class="form-grid">
              <label class="field">
                <span>${a(this.hass, "target")}</span>
                <select .value=${this._targetMode} @change=${(v) => {
      this._targetMode = v.target.value;
    }}>
                  <option value="duration">${a(this.hass, "duration_mode")}</option>
                  <option value="amount">${a(this.hass, "amount_mode")}</option>
                </select>
              </label>
              <label class="field">
                <span>${this._targetMode === "duration" ? a(this.hass, "duration") : a(this.hass, "amount")}</span>
                <input type="number" min="0.001" step=${this._targetMode === "duration" ? "1" : "0.1"} .value=${String(this._targetValue)} @input=${(v) => {
      this._targetValue = Number(v.target.value);
    }} />
                <span>${this._targetMode === "duration" ? a(this.hass, "seconds") : a(this.hass, "liters")}</span>
              </label>
              ${this._targetMode === "amount" ? l`<label class="field"><span>${a(this.hass, "hard_limit")}</span><input type="number" min="0.001" max="14400" step="1" .value=${String(this._hardLimit)} @input=${(v) => {
      this._hardLimit = Number(v.target.value);
    }} /><span>${a(this.hass, "seconds")}</span></label>` : c}
            </div>
          </section>

          ${this._error ? l`<div class="error" role="alert">${this._error}</div>` : c}
          <div class="actions">
            ${$.includes("create") ? l`<button ?disabled=${this._busy || n?.state === "on" || !m} @click=${this.request}><ha-icon icon="mdi:playlist-plus"></ha-icon>${a(this.hass, "create")}</button>` : c}
            ${$.includes("start") ? l`<button class="primary" ?disabled=${this._busy || n?.state === "on" || !m} @click=${this.request}><ha-icon icon="mdi:play"></ha-icon>${a(this.hass, "start")}</button>` : c}
            ${$.includes("pause") ? l`<button ?disabled=${this._busy || !f?.requestId} @click=${() => this.requestAction("pause_request")}><ha-icon icon="mdi:pause"></ha-icon>${a(this.hass, "pause")}</button>` : c}
            ${$.includes("resume") ? l`<button ?disabled=${this._busy || !f?.requestId} @click=${() => this.requestAction("resume_request")}><ha-icon icon="mdi:play-pause"></ha-icon>${a(this.hass, "resume")}</button>` : c}
            ${$.includes("stop") ? l`<button class="danger" ?disabled=${this._busy || !f} @click=${() => this.stop()}><ha-icon icon="mdi:stop-circle-outline"></ha-icon>${a(this.hass, "stop")}</button>` : c}
            ${$.includes("stop_skip") ? l`<button class="danger" ?disabled=${this._busy || !f} @click=${() => this.stop(!0)}><ha-icon icon="mdi:skip-next-circle-outline"></ha-icon>${a(this.hass, "stop_skip")}</button>` : c}
            ${$.includes("suspend") ? l`<button ?disabled=${this._busy || !m || h?.state === "on"} @click=${() => m && this.perform("suspend_automatic", { ...m, until: new Date(Date.now() + 864e5).toISOString() })}><ha-icon icon="mdi:calendar-clock"></ha-icon>${a(this.hass, "suspend_24h")}</button>` : c}
            ${$.includes("resume_auto") ? l`<button ?disabled=${this._busy || !m} @click=${() => m && this.perform("resume_automatic", m)}><ha-icon icon="mdi:calendar-check"></ha-icon>${a(this.hass, "resume_automatic")}</button>` : c}
            ${$.includes("archive") ? l`<button ?disabled=${this._busy || !m || h?.state === "on"} @click=${() => m && this.perform("archive_zone", m, a(this.hass, "confirm_archive"))}><ha-icon icon="mdi:archive-arrow-down-outline"></ha-icon>${a(this.hass, "archive")}</button>` : c}
            ${$.includes("restore") ? l`<button ?disabled=${this._busy || !m || h?.state !== "on"} @click=${() => m && this.perform("restore_zone", m)}><ha-icon icon="mdi:archive-arrow-up-outline"></ha-icon>${a(this.hass, "restore")}</button>` : c}
          </div>
        </div>
      </ha-card>
    `;
  }
};
j.styles = Ht, j.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 },
  _targetMode: { state: !0 },
  _targetValue: { state: !0 },
  _hardLimit: { state: !0 },
  _busy: { state: !0 },
  _error: { state: !0 }
};
let it = j;
const ze = [
  ["irrigation-manager-overview-card", et],
  ["irrigation-manager-zone-card", it],
  ["irrigation-manager-overview-card-editor", xe],
  ["irrigation-manager-zone-card-editor", ke]
];
for (const [s, t] of ze)
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
