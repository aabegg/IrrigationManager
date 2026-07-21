const U = globalThis, G = U.ShadowRoot && (U.ShadyCSS === void 0 || U.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype, J = /* @__PURE__ */ Symbol(), tt = /* @__PURE__ */ new WeakMap();
let mt = class {
  constructor(t, e, i) {
    if (this._$cssResult$ = !0, i !== J) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
    this.cssText = t, this.t = e;
  }
  get styleSheet() {
    let t = this.o;
    const e = this.t;
    if (G && t === void 0) {
      const i = e !== void 0 && e.length === 1;
      i && (t = tt.get(e)), t === void 0 && ((this.o = t = new CSSStyleSheet()).replaceSync(this.cssText), i && tt.set(e, t));
    }
    return t;
  }
  toString() {
    return this.cssText;
  }
};
const Ct = (n) => new mt(typeof n == "string" ? n : n + "", void 0, J), ft = (n, ...t) => {
  const e = n.length === 1 ? n[0] : t.reduce((i, s, r) => i + ((a) => {
    if (a._$cssResult$ === !0) return a.cssText;
    if (typeof a == "number") return a;
    throw Error("Value passed to 'css' function must be a 'css' function result: " + a + ". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.");
  })(s) + n[r + 1], n[0]);
  return new mt(e, n, J);
}, Mt = (n, t) => {
  if (G) n.adoptedStyleSheets = t.map((e) => e instanceof CSSStyleSheet ? e : e.styleSheet);
  else for (const e of t) {
    const i = document.createElement("style"), s = U.litNonce;
    s !== void 0 && i.setAttribute("nonce", s), i.textContent = e.cssText, n.appendChild(i);
  }
}, et = G ? (n) => n : (n) => n instanceof CSSStyleSheet ? ((t) => {
  let e = "";
  for (const i of t.cssRules) e += i.cssText;
  return Ct(e);
})(n) : n;
const { is: qt, defineProperty: Nt, getOwnPropertyDescriptor: Pt, getOwnPropertyNames: Tt, getOwnPropertySymbols: Ut, getPrototypeOf: Ot } = Object, D = globalThis, it = D.trustedTypes, Rt = it ? it.emptyScript : "", Lt = D.reactiveElementPolyfillSupport, M = (n, t) => n, F = { toAttribute(n, t) {
  switch (t) {
    case Boolean:
      n = n ? Rt : null;
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
} }, yt = (n, t) => !qt(n, t), st = { attribute: !0, type: String, converter: F, reflect: !1, useDefault: !1, hasChanged: yt };
Symbol.metadata ??= /* @__PURE__ */ Symbol("metadata"), D.litPropertyMetadata ??= /* @__PURE__ */ new WeakMap();
let S = class extends HTMLElement {
  static addInitializer(t) {
    this._$Ei(), (this.l ??= []).push(t);
  }
  static get observedAttributes() {
    return this.finalize(), this._$Eh && [...this._$Eh.keys()];
  }
  static createProperty(t, e = st) {
    if (e.state && (e.attribute = !1), this._$Ei(), this.prototype.hasOwnProperty(t) && ((e = Object.create(e)).wrapped = !0), this.elementProperties.set(t, e), !e.noAccessor) {
      const i = /* @__PURE__ */ Symbol(), s = this.getPropertyDescriptor(t, i, e);
      s !== void 0 && Nt(this.prototype, t, s);
    }
  }
  static getPropertyDescriptor(t, e, i) {
    const { get: s, set: r } = Pt(this.prototype, t) ?? { get() {
      return this[e];
    }, set(a) {
      this[e] = a;
    } };
    return { get: s, set(a) {
      const p = s?.call(this);
      r?.call(this, a), this.requestUpdate(t, p, i);
    }, configurable: !0, enumerable: !0 };
  }
  static getPropertyOptions(t) {
    return this.elementProperties.get(t) ?? st;
  }
  static _$Ei() {
    if (this.hasOwnProperty(M("elementProperties"))) return;
    const t = Ot(this);
    t.finalize(), t.l !== void 0 && (this.l = [...t.l]), this.elementProperties = new Map(t.elementProperties);
  }
  static finalize() {
    if (this.hasOwnProperty(M("finalized"))) return;
    if (this.finalized = !0, this._$Ei(), this.hasOwnProperty(M("properties"))) {
      const e = this.properties, i = [...Tt(e), ...Ut(e)];
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
      for (const s of i) e.unshift(et(s));
    } else t !== void 0 && e.push(et(t));
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
    return Mt(t, this.constructor.elementStyles), t;
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
      const r = (i.converter?.toAttribute !== void 0 ? i.converter : F).toAttribute(e, i.type);
      this._$Em = t, r == null ? this.removeAttribute(s) : this.setAttribute(s, r), this._$Em = null;
    }
  }
  _$AK(t, e) {
    const i = this.constructor, s = i._$Eh.get(t);
    if (s !== void 0 && this._$Em !== s) {
      const r = i.getPropertyOptions(s), a = typeof r.converter == "function" ? { fromAttribute: r.converter } : r.converter?.fromAttribute !== void 0 ? r.converter : F;
      this._$Em = s;
      const p = a.fromAttribute(e, r.type);
      this[s] = p ?? this._$Ej?.get(s) ?? p, this._$Em = null;
    }
  }
  requestUpdate(t, e, i, s = !1, r) {
    if (t !== void 0) {
      const a = this.constructor;
      if (s === !1 && (r = this[t]), i ??= a.getPropertyOptions(t), !((i.hasChanged ?? yt)(r, e) || i.useDefault && i.reflect && r === this._$Ej?.get(t) && !this.hasAttribute(a._$Eu(t, i)))) return;
      this.C(t, e, i);
    }
    this.isUpdatePending === !1 && (this._$ES = this._$EP());
  }
  C(t, e, { useDefault: i, reflect: s, wrapped: r }, a) {
    i && !(this._$Ej ??= /* @__PURE__ */ new Map()).has(t) && (this._$Ej.set(t, a ?? e ?? this[t]), r !== !0 || a !== void 0) || (this._$AL.has(t) || (this.hasUpdated || i || (e = void 0), this._$AL.set(t, e)), s === !0 && this._$Em !== t && (this._$Eq ??= /* @__PURE__ */ new Set()).add(t));
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
        for (const [s, r] of this._$Ep) this[s] = r;
        this._$Ep = void 0;
      }
      const i = this.constructor.elementProperties;
      if (i.size > 0) for (const [s, r] of i) {
        const { wrapped: a } = r, p = this[s];
        a !== !0 || this._$AL.has(s) || p === void 0 || this.C(s, void 0, r, p);
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
S.elementStyles = [], S.shadowRootOptions = { mode: "open" }, S[M("elementProperties")] = /* @__PURE__ */ new Map(), S[M("finalized")] = /* @__PURE__ */ new Map(), Lt?.({ ReactiveElement: S }), (D.reactiveElementVersions ??= []).push("2.1.2");
const Q = globalThis, nt = (n) => n, O = Q.trustedTypes, rt = O ? O.createPolicy("lit-html", { createHTML: (n) => n }) : void 0, $t = "$lit$", v = `lit$${Math.random().toFixed(9).slice(2)}$`, vt = "?" + v, It = `<${vt}>`, E = document, q = () => E.createComment(""), N = (n) => n === null || typeof n != "object" && typeof n != "function", Y = Array.isArray, Ht = (n) => Y(n) || typeof n?.[Symbol.iterator] == "function", B = `[ 	
\f\r]`, C = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g, ot = /-->/g, at = />/g, b = RegExp(`>|${B}(?:([^\\s"'>=/]+)(${B}*=${B}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`, "g"), ct = /'/g, ht = /"/g, bt = /^(?:script|style|textarea|title)$/i, Dt = (n) => (t, ...e) => ({ _$litType$: n, strings: t, values: e }), d = Dt(1), k = /* @__PURE__ */ Symbol.for("lit-noChange"), c = /* @__PURE__ */ Symbol.for("lit-nothing"), lt = /* @__PURE__ */ new WeakMap(), A = E.createTreeWalker(E, 129);
function At(n, t) {
  if (!Y(n) || !n.hasOwnProperty("raw")) throw Error("invalid template strings array");
  return rt !== void 0 ? rt.createHTML(t) : t;
}
const Vt = (n, t) => {
  const e = n.length - 1, i = [];
  let s, r = t === 2 ? "<svg>" : t === 3 ? "<math>" : "", a = C;
  for (let p = 0; p < e; p++) {
    const h = n[p];
    let _, g, l = -1, m = 0;
    for (; m < h.length && (a.lastIndex = m, g = a.exec(h), g !== null); ) m = a.lastIndex, a === C ? g[1] === "!--" ? a = ot : g[1] !== void 0 ? a = at : g[2] !== void 0 ? (bt.test(g[2]) && (s = RegExp("</" + g[2], "g")), a = b) : g[3] !== void 0 && (a = b) : a === b ? g[0] === ">" ? (a = s ?? C, l = -1) : g[1] === void 0 ? l = -2 : (l = a.lastIndex - g[2].length, _ = g[1], a = g[3] === void 0 ? b : g[3] === '"' ? ht : ct) : a === ht || a === ct ? a = b : a === ot || a === at ? a = C : (a = b, s = void 0);
    const f = a === b && n[p + 1].startsWith("/>") ? " " : "";
    r += a === C ? h + It : l >= 0 ? (i.push(_), h.slice(0, l) + $t + h.slice(l) + v + f) : h + v + (l === -2 ? p : f);
  }
  return [At(n, r + (n[e] || "<?>") + (t === 2 ? "</svg>" : t === 3 ? "</math>" : "")), i];
};
class P {
  constructor({ strings: t, _$litType$: e }, i) {
    let s;
    this.parts = [];
    let r = 0, a = 0;
    const p = t.length - 1, h = this.parts, [_, g] = Vt(t, e);
    if (this.el = P.createElement(_, i), A.currentNode = this.el.content, e === 2 || e === 3) {
      const l = this.el.content.firstChild;
      l.replaceWith(...l.childNodes);
    }
    for (; (s = A.nextNode()) !== null && h.length < p; ) {
      if (s.nodeType === 1) {
        if (s.hasAttributes()) for (const l of s.getAttributeNames()) if (l.endsWith($t)) {
          const m = g[a++], f = s.getAttribute(l).split(v), $ = /([.?@])?(.*)/.exec(m);
          h.push({ type: 1, index: r, name: $[2], strings: f, ctor: $[1] === "." ? Wt : $[1] === "?" ? Ft : $[1] === "@" ? jt : V }), s.removeAttribute(l);
        } else l.startsWith(v) && (h.push({ type: 6, index: r }), s.removeAttribute(l));
        if (bt.test(s.tagName)) {
          const l = s.textContent.split(v), m = l.length - 1;
          if (m > 0) {
            s.textContent = O ? O.emptyScript : "";
            for (let f = 0; f < m; f++) s.append(l[f], q()), A.nextNode(), h.push({ type: 2, index: ++r });
            s.append(l[m], q());
          }
        }
      } else if (s.nodeType === 8) if (s.data === vt) h.push({ type: 2, index: r });
      else {
        let l = -1;
        for (; (l = s.data.indexOf(v, l + 1)) !== -1; ) h.push({ type: 7, index: r }), l += v.length - 1;
      }
      r++;
    }
  }
  static createElement(t, e) {
    const i = E.createElement("template");
    return i.innerHTML = t, i;
  }
}
function z(n, t, e = n, i) {
  if (t === k) return t;
  let s = i !== void 0 ? e._$Co?.[i] : e._$Cl;
  const r = N(t) ? void 0 : t._$litDirective$;
  return s?.constructor !== r && (s?._$AO?.(!1), r === void 0 ? s = void 0 : (s = new r(n), s._$AT(n, e, i)), i !== void 0 ? (e._$Co ??= [])[i] = s : e._$Cl = s), s !== void 0 && (t = z(n, s._$AS(n, t.values), s, i)), t;
}
class Bt {
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
    A.currentNode = s;
    let r = A.nextNode(), a = 0, p = 0, h = i[0];
    for (; h !== void 0; ) {
      if (a === h.index) {
        let _;
        h.type === 2 ? _ = new T(r, r.nextSibling, this, t) : h.type === 1 ? _ = new h.ctor(r, h.name, h.strings, this, t) : h.type === 6 && (_ = new Zt(r, this, t)), this._$AV.push(_), h = i[++p];
      }
      a !== h?.index && (r = A.nextNode(), a++);
    }
    return A.currentNode = E, s;
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
    t = z(this, t, e), N(t) ? t === c || t == null || t === "" ? (this._$AH !== c && this._$AR(), this._$AH = c) : t !== this._$AH && t !== k && this._(t) : t._$litType$ !== void 0 ? this.$(t) : t.nodeType !== void 0 ? this.T(t) : Ht(t) ? this.k(t) : this._(t);
  }
  O(t) {
    return this._$AA.parentNode.insertBefore(t, this._$AB);
  }
  T(t) {
    this._$AH !== t && (this._$AR(), this._$AH = this.O(t));
  }
  _(t) {
    this._$AH !== c && N(this._$AH) ? this._$AA.nextSibling.data = t : this.T(E.createTextNode(t)), this._$AH = t;
  }
  $(t) {
    const { values: e, _$litType$: i } = t, s = typeof i == "number" ? this._$AC(t) : (i.el === void 0 && (i.el = P.createElement(At(i.h, i.h[0]), this.options)), i);
    if (this._$AH?._$AD === s) this._$AH.p(e);
    else {
      const r = new Bt(s, this), a = r.u(this.options);
      r.p(e), this.T(a), this._$AH = r;
    }
  }
  _$AC(t) {
    let e = lt.get(t.strings);
    return e === void 0 && lt.set(t.strings, e = new P(t)), e;
  }
  k(t) {
    Y(this._$AH) || (this._$AH = [], this._$AR());
    const e = this._$AH;
    let i, s = 0;
    for (const r of t) s === e.length ? e.push(i = new T(this.O(q()), this.O(q()), this, this.options)) : i = e[s], i._$AI(r), s++;
    s < e.length && (this._$AR(i && i._$AB.nextSibling, s), e.length = s);
  }
  _$AR(t = this._$AA.nextSibling, e) {
    for (this._$AP?.(!1, !0, e); t !== this._$AB; ) {
      const i = nt(t).nextSibling;
      nt(t).remove(), t = i;
    }
  }
  setConnected(t) {
    this._$AM === void 0 && (this._$Cv = t, this._$AP?.(t));
  }
}
class V {
  get tagName() {
    return this.element.tagName;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  constructor(t, e, i, s, r) {
    this.type = 1, this._$AH = c, this._$AN = void 0, this.element = t, this.name = e, this._$AM = s, this.options = r, i.length > 2 || i[0] !== "" || i[1] !== "" ? (this._$AH = Array(i.length - 1).fill(new String()), this.strings = i) : this._$AH = c;
  }
  _$AI(t, e = this, i, s) {
    const r = this.strings;
    let a = !1;
    if (r === void 0) t = z(this, t, e, 0), a = !N(t) || t !== this._$AH && t !== k, a && (this._$AH = t);
    else {
      const p = t;
      let h, _;
      for (t = r[0], h = 0; h < r.length - 1; h++) _ = z(this, p[i + h], e, h), _ === k && (_ = this._$AH[h]), a ||= !N(_) || _ !== this._$AH[h], _ === c ? t = c : t !== c && (t += (_ ?? "") + r[h + 1]), this._$AH[h] = _;
    }
    a && !s && this.j(t);
  }
  j(t) {
    t === c ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, t ?? "");
  }
}
class Wt extends V {
  constructor() {
    super(...arguments), this.type = 3;
  }
  j(t) {
    this.element[this.name] = t === c ? void 0 : t;
  }
}
class Ft extends V {
  constructor() {
    super(...arguments), this.type = 4;
  }
  j(t) {
    this.element.toggleAttribute(this.name, !!t && t !== c);
  }
}
class jt extends V {
  constructor(t, e, i, s, r) {
    super(t, e, i, s, r), this.type = 5;
  }
  _$AI(t, e = this) {
    if ((t = z(this, t, e, 0) ?? c) === k) return;
    const i = this._$AH, s = t === c && i !== c || t.capture !== i.capture || t.once !== i.once || t.passive !== i.passive, r = t !== c && (i === c || s);
    s && this.element.removeEventListener(this.name, this, i), r && this.element.addEventListener(this.name, this, t), this._$AH = t;
  }
  handleEvent(t) {
    typeof this._$AH == "function" ? this._$AH.call(this.options?.host ?? this.element, t) : this._$AH.handleEvent(t);
  }
}
class Zt {
  constructor(t, e, i) {
    this.element = t, this.type = 6, this._$AN = void 0, this._$AM = e, this.options = i;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  _$AI(t) {
    z(this, t);
  }
}
const Kt = Q.litHtmlPolyfillSupport;
Kt?.(P, T), (Q.litHtmlVersions ??= []).push("3.3.3");
const Gt = (n, t, e) => {
  const i = e?.renderBefore ?? t;
  let s = i._$litPart$;
  if (s === void 0) {
    const r = e?.renderBefore ?? null;
    i._$litPart$ = s = new T(t.insertBefore(q(), r), r, void 0, e ?? {});
  }
  return s._$AI(n), s;
};
const X = globalThis;
class x extends S {
  constructor() {
    super(...arguments), this.renderOptions = { host: this }, this._$Do = void 0;
  }
  createRenderRoot() {
    const t = super.createRenderRoot();
    return this.renderOptions.renderBefore ??= t.firstChild, t;
  }
  update(t) {
    const e = this.render();
    this.hasUpdated || (this.renderOptions.isConnected = this.isConnected), super.update(t), this._$Do = Gt(e, this.renderRoot, this.renderOptions);
  }
  connectedCallback() {
    super.connectedCallback(), this._$Do?.setConnected(!0);
  }
  disconnectedCallback() {
    super.disconnectedCallback(), this._$Do?.setConnected(!1);
  }
  render() {
    return k;
  }
}
x._$litElement$ = !0, x.finalized = !0, X.litElementHydrateSupport?.({ LitElement: x });
const Jt = X.litElementPolyfillSupport;
Jt?.({ LitElement: x });
(X.litElementVersions ??= []).push("4.2.2");
const wt = "irrigation_manager", Qt = "create_manual", Yt = /* @__PURE__ */ new Set(["unknown", "unavailable"]);
function u(n, t) {
  return t ? n.states[t] : void 0;
}
function j(n) {
  return !!(n && !Yt.has(n.state));
}
function y(n, t) {
  const e = n?.attributes[t];
  return typeof e == "string" && e ? e : void 0;
}
function dt(n, t) {
  const e = n?.attributes[t];
  return typeof e == "number" && Number.isFinite(e) ? e : void 0;
}
function W(n, t) {
  if (!t || y(n, "zone_subentry_id") !== t)
    return;
  const e = y(n, "request_id"), i = y(n, "execution_id");
  return e || i ? { requestId: e, executionId: i } : void 0;
}
function xt(n) {
  const t = dt(n, "target_value"), e = dt(n, "remaining_value");
  if (!(t === void 0 || e === void 0 || t <= 0))
    return Math.max(0, Math.min(100, (t - e) / t * 100));
}
function Et(n) {
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
function Xt(n, t) {
  n.dispatchEvent(
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
    no_window: "No watering window available"
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
    no_window: "Kein Bewässerungsfenster verfügbar"
  }
};
function o(n, t) {
  const e = n.language?.toLowerCase().startsWith("de") ? "de" : "en";
  return St[e][t];
}
function kt(n, t) {
  return t in St.en ? o(n, t) : t.replaceAll("_", " ");
}
function w(n, t) {
  if (!t) return o(n, "missing");
  if (t.state === "unavailable") return o(n, "unavailable");
  if (t.state === "unknown" || t.state === "") return o(n, "unknown");
  if (n.formatEntityState) return n.formatEntityState(t);
  const e = t.attributes.unit_of_measurement;
  return `${kt(n, t.state)}${e ? ` ${e}` : ""}`;
}
const zt = ft`
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
`, te = ft`
  :host { display: block; }
  .editor { display: grid; gap: 18px; padding: 8px 0; }
  section { display: grid; gap: 10px; }
  h3 { margin: 0; font-size: 1rem; }
  label.selector { display: grid; gap: 5px; color: var(--secondary-text-color); }
  .checks { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 6px 12px; }
  .check { display: flex; align-items: center; gap: 8px; min-height: 34px; }
  input[type="checkbox"] { width: 18px; height: 18px; accent-color: var(--primary-color); }
  select { min-height: 40px; padding: 8px; color: var(--primary-text-color); background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 8px; }
`, ut = [
  ["status_entity", "Installation status"],
  ["emergency_entity", "Emergency stop"],
  ["lock_entity", "Installation safety lock"],
  ["active_zone_entity", "Active zone / progress"],
  ["dose_entity", "Current dose"],
  ["pending_entity", "Open requests"],
  ["next_entity", "Next irrigation"],
  ["today_consumption_entity", "Today's consumption"],
  ["month_consumption_entity", "Monthly consumption"],
  ["model_quality_entity", "Model quality"]
], pt = [
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
  ["quality_entity", "Measurement quality"]
], ee = {
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
}, ie = ["active", "pending", "next", "today", "month", "quality"], se = ["stop", "emergency"], ne = ["balance", "next", "total", "recent", "quality"], re = ["create", "start", "pause", "resume", "stop"], L = class L extends x {
  setConfig(t) {
    this._config = { ...t };
  }
  updateValue(t, e) {
    const i = { ...this._config, [t]: e || void 0 };
    e || delete i[t], this._config = i, Xt(this, i);
  }
  entitySelector(t, e, i) {
    const s = this.hass.language.toLowerCase().startsWith("de") ? ee[e] ?? e : e;
    return d`
      <label class="selector">
        <span>${s}${i ? " *" : ""}</span>
        <ha-selector
          .hass=${this.hass}
          .selector=${{ entity: { filter: { integration: "irrigation_manager" } } }}
          .value=${this._config[t] ?? ""}
          @value-changed=${(r) => this.updateValue(t, r.detail.value)}
        ></ha-selector>
      </label>
    `;
  }
  displayMode() {
    return d`
      <label class="selector">
        <span>${o(this.hass, "display")}</span>
        <select
          .value=${this._config.display_mode ?? "detailed"}
          @change=${(t) => this.updateValue("display_mode", t.target.value)}
        >
          <option value="compact">${o(this.hass, "compact")}</option>
          <option value="detailed">${o(this.hass, "detailed")}</option>
        </select>
      </label>
    `;
  }
  choices(t, e) {
    const i = this._config[t] ?? e;
    return d`
      <div class="checks">
        ${e.map(
      (s) => d`
            <label class="check">
              <input
                type="checkbox"
                .checked=${i.includes(s)}
                @change=${(r) => {
        const a = r.target.checked;
        this.updateValue(
          t,
          a ? [...i, s] : i.filter((p) => p !== s)
        );
      }}
              />
              ${o(this.hass, s)}
            </label>
          `
    )}
      </div>
    `;
  }
};
L.styles = te, L.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 }
};
let R = L;
class oe extends R {
  render() {
    return !this.hass || !this._config ? c : d`
      <div class="editor">
        <section>
          <h3>${o(this.hass, "required_entity")}</h3>
          ${this.entitySelector("status_entity", ut[0][1], !0)}
        </section>
        <section>
          <h3>${o(this.hass, "optional_entities")}</h3>
          ${ut.slice(1).map(([t, e]) => this.entitySelector(t, e, !1))}
        </section>
        <section>${this.displayMode()}</section>
        <section>
          <h3>${o(this.hass, "metrics")}</h3>
          ${this.choices("visible_metrics", ie)}
        </section>
        <section>
          <h3>${o(this.hass, "actions")}</h3>
          ${this.choices("visible_actions", se)}
        </section>
      </div>
    `;
  }
}
class ae extends R {
  render() {
    return !this.hass || !this._config ? c : d`
      <div class="editor">
        <section>
          <h3>${o(this.hass, "required_entity")}</h3>
          ${this.entitySelector("zone_entity", pt[0][1], !0)}
        </section>
        <section>
          <h3>${o(this.hass, "optional_entities")}</h3>
          ${pt.slice(1).map(([t, e]) => this.entitySelector(t, e, !1))}
        </section>
        <section>${this.displayMode()}</section>
        <section>
          <h3>${o(this.hass, "metrics")}</h3>
          ${this.choices("visible_metrics", ne)}
        </section>
        <section>
          <h3>${o(this.hass, "actions")}</h3>
          ${this.choices("visible_actions", re)}
        </section>
      </div>
    `;
  }
}
const _t = ["active", "pending", "next", "today", "month", "quality"], ce = ["stop", "emergency"], I = class I extends x {
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
    return (this._config.visible_metrics ?? _t).includes(t) ? d`<div class="metric"><span>${e}</span><strong>${w(this.hass, i)}</strong></div>` : c;
  }
  async call(t, e) {
    if (!window.confirm(e)) return;
    const i = u(this.hass, this._config.status_entity), s = y(i, "config_entry_id");
    if (!s) {
      this._error = o(this.hass, "configuration_error");
      return;
    }
    this._busy = !0, this._error = void 0;
    try {
      await this.hass.callService(wt, t, { config_entry_id: s });
    } catch (r) {
      this._error = `${o(this.hass, "action_failed")}: ${r instanceof Error ? r.message : String(r)}`;
    } finally {
      this._busy = !1;
    }
  }
  render() {
    if (!this.hass || !this._config) return c;
    const t = u(this.hass, this._config.status_entity), e = u(this.hass, this._config.emergency_entity), i = u(this.hass, this._config.lock_entity), s = u(this.hass, this._config.active_zone_entity), r = xt(s), a = this._config.visible_actions ?? ce, p = t?.state ?? "unavailable", h = e?.state === "on" || i?.state === "on";
    return d`
      <ha-card>
        <div class="card ${this._config.display_mode === "compact" ? "compact" : ""}">
          <header>
            <div class="hero">
              <ha-icon .icon=${Et(p)}></ha-icon>
              <div>
                <h2>${this._config.name ?? o(this.hass, "overview")}</h2>
                <strong>${j(t) ? kt(this.hass, t.state) : w(this.hass, t)}</strong>
              </div>
            </div>
          </header>

          ${h ? d`<div class="warning danger"><ha-icon icon="mdi:lock-alert-outline"></ha-icon><span>${e?.state === "on" ? o(this.hass, "emergency_stop") : o(this.hass, "safety_lock")}${y(i, "reason") ? `: ${y(i, "reason")}` : ""}</span></div>` : c}

          ${(this._config.visible_metrics ?? _t).includes("active") && s ? d`
                <section>
                  <h3>${o(this.hass, "active_zone")}</h3>
                  <strong>${w(this.hass, s)}</strong>
                  ${this._config.dose_entity ? d`<div class="secondary">${o(this.hass, "dose")}: ${w(this.hass, u(this.hass, this._config.dose_entity))}</div>` : c}
                  ${r === void 0 ? c : d`<div class="secondary">${o(this.hass, "progress")}: ${Math.round(r)}%</div><progress max="100" .value=${r} aria-label=${o(this.hass, "progress")}></progress>`}
                </section>
              ` : c}

          <div class="metrics details">
            ${this.metric("pending", o(this.hass, "pending"), u(this.hass, this._config.pending_entity))}
            ${this.metric("next", o(this.hass, "next"), u(this.hass, this._config.next_entity))}
            ${this.metric("today", o(this.hass, "today"), u(this.hass, this._config.today_consumption_entity))}
            ${this.metric("month", o(this.hass, "month"), u(this.hass, this._config.month_consumption_entity))}
            ${this.metric("quality", o(this.hass, "model_quality"), u(this.hass, this._config.model_quality_entity))}
          </div>

          ${this._error ? d`<div class="error" role="alert">${this._error}</div>` : c}
          <div class="actions">
            ${a.includes("stop") ? d`<button class="danger" ?disabled=${this._busy || !j(t)} @click=${() => this.call("stop", o(this.hass, "confirm_stop"))}><ha-icon icon="mdi:stop-circle-outline"></ha-icon>${o(this.hass, "stop")}</button>` : c}
            ${a.includes("emergency") ? d`<button class="danger" ?disabled=${this._busy} @click=${() => this.call("emergency_stop", o(this.hass, "confirm_emergency"))}><ha-icon icon="mdi:alert-octagon-outline"></ha-icon>${o(this.hass, "emergency")}</button>` : c}
          </div>
        </div>
      </ha-card>
    `;
  }
};
I.styles = zt, I.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 },
  _busy: { state: !0 },
  _error: { state: !0 }
};
let Z = I;
const gt = ["balance", "next", "total", "recent", "quality"], he = ["create", "start", "pause", "resume", "stop"], H = class H extends x {
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
    return (this._config.visible_metrics ?? gt).includes(t) ? d`<div class="metric"><span>${e}</span><strong>${w(this.hass, i)}</strong></div>` : c;
  }
  context() {
    const t = u(this.hass, this._config.zone_entity), e = y(t, "config_entry_id"), i = y(t, "zone_subentry_id");
    return e && i ? { config_entry_id: e, zone_subentry_id: i } : void 0;
  }
  async perform(t, e, i) {
    if (!(i && !window.confirm(i))) {
      this._busy = !0, this._error = void 0;
      try {
        await this.hass.callService(wt, t, e);
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
    const e = this._targetMode === "duration" ? { duration: this._targetValue } : { amount: this._targetValue, hard_time_limit: this._hardLimit };
    await this.perform(Qt, { ...t, ...e });
  }
  async requestAction(t) {
    const e = this.context(), i = u(this.hass, this._config.request_entity), s = W(i, e?.zone_subentry_id);
    if (!e || !s?.requestId) {
      this._error = o(this.hass, "configuration_error");
      return;
    }
    await this.perform(t, {
      config_entry_id: e.config_entry_id,
      request_id: s.requestId
    });
  }
  async stop() {
    const t = this.context(), e = u(this.hass, this._config.request_entity), i = W(e, t?.zone_subentry_id);
    if (!t || !i) {
      this._error = o(this.hass, "configuration_error");
      return;
    }
    const s = i.executionId ? { execution_id: i.executionId } : { request_id: i.requestId };
    await this.perform("stop", { config_entry_id: t.config_entry_id, ...s }, o(this.hass, "confirm_stop"));
  }
  render() {
    if (!this.hass || !this._config) return c;
    const t = u(this.hass, this._config.zone_entity), e = u(this.hass, this._config.automation_needed_entity), i = u(this.hass, this._config.safety_lock_entity), s = u(this.hass, this._config.quality_entity), r = u(this.hass, this._config.active_zone_entity), a = u(this.hass, this._config.request_entity), p = this.context(), h = W(a, p?.zone_subentry_id), _ = xt(r), g = this._config.visible_metrics ?? gt, l = this._config.visible_actions ?? he, m = this._config.name ?? t?.attributes.friendly_name ?? o(this.hass, "zone"), f = s?.state ?? y(t, "measurement_quality");
    return d`
      <ha-card>
        <div class="card ${this._config.display_mode === "compact" ? "compact" : ""}">
          <header>
            <div class="hero">
              <ha-icon .icon=${Et(i?.state === "on" ? "safety_lock" : e?.state ?? "unknown")}></ha-icon>
              <div>
                <h2>${m}</h2>
                <strong>${i?.state === "on" ? o(this.hass, "locked") : e?.state === "on" ? o(this.hass, "automation_needed") : e?.state === "off" ? o(this.hass, "automation_not_needed") : w(this.hass, e)}</strong>
              </div>
            </div>
          </header>

          ${i?.state === "on" ? d`<div class="warning danger"><ha-icon icon="mdi:lock-alert-outline"></ha-icon><span>${o(this.hass, "safety_lock")}${y(i, "reason") ? `: ${y(i, "reason")}` : ""}</span></div>` : c}
          ${f === "estimated" ? d`<div class="warning"><ha-icon icon="mdi:calculator-variant-outline"></ha-icon><span>${o(this.hass, "warning_estimated")}</span></div>` : f === "unknown" ? d`<div class="warning"><ha-icon icon="mdi:help-circle-outline"></ha-icon><span>${o(this.hass, "warning_unknown")}</span></div>` : c}

          ${h && r && j(r) && _ !== void 0 ? d`<section><h3>${o(this.hass, "progress")}</h3><strong>${w(this.hass, r)} · ${Math.round(_)}%</strong><progress max="100" .value=${_} aria-label=${o(this.hass, "progress")}></progress></section>` : c}

          <div class="metrics">
            ${this.metric("balance", o(this.hass, "water_balance"), u(this.hass, this._config.deficit_entity))}
            ${this.metric("balance", o(this.hass, "target"), u(this.hass, this._config.target_entity))}
            ${g.includes("balance") ? this.metric("balance", o(this.hass, "explanation"), u(this.hass, this._config.planning_reason_entity)) : c}
            ${this.metric("next", o(this.hass, "next_window"), u(this.hass, this._config.next_window_entity))}
            ${this.metric("total", o(this.hass, "total"), t)}
            ${this.metric("recent", o(this.hass, "last_delivered"), u(this.hass, this._config.last_delivered_entity))}
            ${this.metric("recent", o(this.hass, "last_duration"), u(this.hass, this._config.last_duration_entity))}
            ${this.metric("quality", o(this.hass, "quality"), s)}
          </div>

          <section class="details">
            <h3>${o(this.hass, "manual")}</h3>
            <div class="form-grid">
              <label class="field">
                <span>${o(this.hass, "target")}</span>
                <select .value=${this._targetMode} @change=${($) => {
      this._targetMode = $.target.value;
    }}>
                  <option value="duration">${o(this.hass, "duration_mode")}</option>
                  <option value="amount">${o(this.hass, "amount_mode")}</option>
                </select>
              </label>
              <label class="field">
                <span>${this._targetMode === "duration" ? o(this.hass, "duration") : o(this.hass, "amount")}</span>
                <input type="number" min="0.001" step=${this._targetMode === "duration" ? "1" : "0.1"} .value=${String(this._targetValue)} @input=${($) => {
      this._targetValue = Number($.target.value);
    }} />
                <span>${this._targetMode === "duration" ? o(this.hass, "seconds") : o(this.hass, "liters")}</span>
              </label>
              ${this._targetMode === "amount" ? d`<label class="field"><span>${o(this.hass, "hard_limit")}</span><input type="number" min="0.001" max="14400" step="1" .value=${String(this._hardLimit)} @input=${($) => {
      this._hardLimit = Number($.target.value);
    }} /><span>${o(this.hass, "seconds")}</span></label>` : c}
            </div>
          </section>

          ${this._error ? d`<div class="error" role="alert">${this._error}</div>` : c}
          <div class="actions">
            ${l.includes("create") ? d`<button ?disabled=${this._busy || i?.state === "on"} @click=${this.request}><ha-icon icon="mdi:playlist-plus"></ha-icon>${o(this.hass, "create")}</button>` : c}
            ${l.includes("start") ? d`<button class="primary" ?disabled=${this._busy || i?.state === "on"} @click=${this.request}><ha-icon icon="mdi:play"></ha-icon>${o(this.hass, "start")}</button>` : c}
            ${l.includes("pause") ? d`<button ?disabled=${this._busy || !h?.requestId} @click=${() => this.requestAction("pause_request")}><ha-icon icon="mdi:pause"></ha-icon>${o(this.hass, "pause")}</button>` : c}
            ${l.includes("resume") ? d`<button ?disabled=${this._busy || !h?.requestId} @click=${() => this.requestAction("resume_request")}><ha-icon icon="mdi:play-pause"></ha-icon>${o(this.hass, "resume")}</button>` : c}
            ${l.includes("stop") ? d`<button class="danger" ?disabled=${this._busy || !h} @click=${this.stop}><ha-icon icon="mdi:stop-circle-outline"></ha-icon>${o(this.hass, "stop")}</button>` : c}
          </div>
        </div>
      </ha-card>
    `;
  }
};
H.styles = zt, H.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 },
  _targetMode: { state: !0 },
  _targetValue: { state: !0 },
  _hardLimit: { state: !0 },
  _busy: { state: !0 },
  _error: { state: !0 }
};
let K = H;
const le = [
  ["irrigation-manager-overview-card", Z],
  ["irrigation-manager-zone-card", K],
  ["irrigation-manager-overview-card-editor", oe],
  ["irrigation-manager-zone-card-editor", ae]
];
for (const [n, t] of le)
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
