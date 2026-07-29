const I = globalThis, rt = I.ShadowRoot && (I.ShadyCSS === void 0 || I.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype, at = /* @__PURE__ */ Symbol(), ht = /* @__PURE__ */ new WeakMap();
let xt = class {
  constructor(t, e, i) {
    if (this._$cssResult$ = !0, i !== at) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
    this.cssText = t, this.t = e;
  }
  get styleSheet() {
    let t = this.o;
    const e = this.t;
    if (rt && t === void 0) {
      const i = e !== void 0 && e.length === 1;
      i && (t = ht.get(e)), t === void 0 && ((this.o = t = new CSSStyleSheet()).replaceSync(this.cssText), i && ht.set(e, t));
    }
    return t;
  }
  toString() {
    return this.cssText;
  }
};
const Tt = (s) => new xt(typeof s == "string" ? s : s + "", void 0, at), wt = (s, ...t) => {
  const e = s.length === 1 ? s[0] : t.reduce((i, r, a) => i + ((o) => {
    if (o._$cssResult$ === !0) return o.cssText;
    if (typeof o == "number") return o;
    throw Error("Value passed to 'css' function must be a 'css' function result: " + o + ". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.");
  })(r) + s[a + 1], s[0]);
  return new xt(e, s, at);
}, Pt = (s, t) => {
  if (rt) s.adoptedStyleSheets = t.map((e) => e instanceof CSSStyleSheet ? e : e.styleSheet);
  else for (const e of t) {
    const i = document.createElement("style"), r = I.litNonce;
    r !== void 0 && i.setAttribute("nonce", r), i.textContent = e.cssText, s.appendChild(i);
  }
}, ct = rt ? (s) => s : (s) => s instanceof CSSStyleSheet ? ((t) => {
  let e = "";
  for (const i of t.cssRules) e += i.cssText;
  return Tt(e);
})(s) : s;
const { is: Ht, defineProperty: Rt, getOwnPropertyDescriptor: Ut, getOwnPropertyNames: It, getOwnPropertySymbols: Lt, getPrototypeOf: Bt } = Object, q = globalThis, dt = q.trustedTypes, Vt = dt ? dt.emptyScript : "", jt = q.reactiveElementPolyfillSupport, C = (s, t) => s, tt = { toAttribute(s, t) {
  switch (t) {
    case Boolean:
      s = s ? Vt : null;
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
} }, At = (s, t) => !Ht(s, t), ut = { attribute: !0, type: String, converter: tt, reflect: !1, useDefault: !1, hasChanged: At };
Symbol.metadata ??= /* @__PURE__ */ Symbol("metadata"), q.litPropertyMetadata ??= /* @__PURE__ */ new WeakMap();
let A = class extends HTMLElement {
  static addInitializer(t) {
    this._$Ei(), (this.l ??= []).push(t);
  }
  static get observedAttributes() {
    return this.finalize(), this._$Eh && [...this._$Eh.keys()];
  }
  static createProperty(t, e = ut) {
    if (e.state && (e.attribute = !1), this._$Ei(), this.prototype.hasOwnProperty(t) && ((e = Object.create(e)).wrapped = !0), this.elementProperties.set(t, e), !e.noAccessor) {
      const i = /* @__PURE__ */ Symbol(), r = this.getPropertyDescriptor(t, i, e);
      r !== void 0 && Rt(this.prototype, t, r);
    }
  }
  static getPropertyDescriptor(t, e, i) {
    const { get: r, set: a } = Ut(this.prototype, t) ?? { get() {
      return this[e];
    }, set(o) {
      this[e] = o;
    } };
    return { get: r, set(o) {
      const d = r?.call(this);
      a?.call(this, o), this.requestUpdate(t, d, i);
    }, configurable: !0, enumerable: !0 };
  }
  static getPropertyOptions(t) {
    return this.elementProperties.get(t) ?? ut;
  }
  static _$Ei() {
    if (this.hasOwnProperty(C("elementProperties"))) return;
    const t = Bt(this);
    t.finalize(), t.l !== void 0 && (this.l = [...t.l]), this.elementProperties = new Map(t.elementProperties);
  }
  static finalize() {
    if (this.hasOwnProperty(C("finalized"))) return;
    if (this.finalized = !0, this._$Ei(), this.hasOwnProperty(C("properties"))) {
      const e = this.properties, i = [...It(e), ...Lt(e)];
      for (const r of i) this.createProperty(r, e[r]);
    }
    const t = this[Symbol.metadata];
    if (t !== null) {
      const e = litPropertyMetadata.get(t);
      if (e !== void 0) for (const [i, r] of e) this.elementProperties.set(i, r);
    }
    this._$Eh = /* @__PURE__ */ new Map();
    for (const [e, i] of this.elementProperties) {
      const r = this._$Eu(e, i);
      r !== void 0 && this._$Eh.set(r, e);
    }
    this.elementStyles = this.finalizeStyles(this.styles);
  }
  static finalizeStyles(t) {
    const e = [];
    if (Array.isArray(t)) {
      const i = new Set(t.flat(1 / 0).reverse());
      for (const r of i) e.unshift(ct(r));
    } else t !== void 0 && e.push(ct(t));
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
    return Pt(t, this.constructor.elementStyles), t;
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
    const i = this.constructor.elementProperties.get(t), r = this.constructor._$Eu(t, i);
    if (r !== void 0 && i.reflect === !0) {
      const a = (i.converter?.toAttribute !== void 0 ? i.converter : tt).toAttribute(e, i.type);
      this._$Em = t, a == null ? this.removeAttribute(r) : this.setAttribute(r, a), this._$Em = null;
    }
  }
  _$AK(t, e) {
    const i = this.constructor, r = i._$Eh.get(t);
    if (r !== void 0 && this._$Em !== r) {
      const a = i.getPropertyOptions(r), o = typeof a.converter == "function" ? { fromAttribute: a.converter } : a.converter?.fromAttribute !== void 0 ? a.converter : tt;
      this._$Em = r;
      const d = o.fromAttribute(e, a.type);
      this[r] = d ?? this._$Ej?.get(r) ?? d, this._$Em = null;
    }
  }
  requestUpdate(t, e, i, r = !1, a) {
    if (t !== void 0) {
      const o = this.constructor;
      if (r === !1 && (a = this[t]), i ??= o.getPropertyOptions(t), !((i.hasChanged ?? At)(a, e) || i.useDefault && i.reflect && a === this._$Ej?.get(t) && !this.hasAttribute(o._$Eu(t, i)))) return;
      this.C(t, e, i);
    }
    this.isUpdatePending === !1 && (this._$ES = this._$EP());
  }
  C(t, e, { useDefault: i, reflect: r, wrapped: a }, o) {
    i && !(this._$Ej ??= /* @__PURE__ */ new Map()).has(t) && (this._$Ej.set(t, o ?? e ?? this[t]), a !== !0 || o !== void 0) || (this._$AL.has(t) || (this.hasUpdated || i || (e = void 0), this._$AL.set(t, e)), r === !0 && this._$Em !== t && (this._$Eq ??= /* @__PURE__ */ new Set()).add(t));
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
        for (const [r, a] of this._$Ep) this[r] = a;
        this._$Ep = void 0;
      }
      const i = this.constructor.elementProperties;
      if (i.size > 0) for (const [r, a] of i) {
        const { wrapped: o } = a, d = this[r];
        o !== !0 || this._$AL.has(r) || d === void 0 || this.C(r, void 0, a, d);
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
A.elementStyles = [], A.shadowRootOptions = { mode: "open" }, A[C("elementProperties")] = /* @__PURE__ */ new Map(), A[C("finalized")] = /* @__PURE__ */ new Map(), jt?.({ ReactiveElement: A }), (q.reactiveElementVersions ??= []).push("2.1.2");
const nt = globalThis, pt = (s) => s, L = nt.trustedTypes, _t = L ? L.createPolicy("lit-html", { createHTML: (s) => s }) : void 0, St = "$lit$", v = `lit$${Math.random().toFixed(9).slice(2)}$`, Et = "?" + v, Ft = `<${Et}>`, w = document, T = () => w.createComment(""), P = (s) => s === null || typeof s != "object" && typeof s != "function", ot = Array.isArray, Wt = (s) => ot(s) || typeof s?.[Symbol.iterator] == "function", J = `[\x20\t\n\f\r]`, D = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g, mt = /-->/g, gt = />/g, $ = RegExp(`>|${J}(?:([^\\s"'>=/]+)(${J}*=${J}*(?:[^\x20\t\n\f\r"'\`<>=]|("|')|))|$)`, "g"), ft = /'/g, yt = /"/g, zt = /^(?:script|style|textarea|title)$/i, Zt = (s) => (t, ...e) => ({ _$litType$: s, strings: t, values: e }), h = Zt(1), z = /* @__PURE__ */ Symbol.for("lit-noChange"), c = /* @__PURE__ */ Symbol.for("lit-nothing"), vt = /* @__PURE__ */ new WeakMap(), b = w.createTreeWalker(w, 129);
function kt(s, t) {
  if (!ot(s) || !s.hasOwnProperty("raw")) throw Error("invalid template strings array");
  return _t !== void 0 ? _t.createHTML(t) : t;
}
const qt = (s, t) => {
  const e = s.length - 1, i = [];
  let r, a = t === 2 ? "<svg>" : t === 3 ? "<math>" : "", o = D;
  for (let d = 0; d < e; d++) {
    const l = s[d];
    let u, m, _ = -1, f = 0;
    for (; f < l.length && (o.lastIndex = f, m = o.exec(l), m !== null); ) f = o.lastIndex, o === D ? m[1] === "!--" ? o = mt : m[1] !== void 0 ? o = gt : m[2] !== void 0 ? (zt.test(m[2]) && (r = RegExp("</" + m[2], "g")), o = $) : m[3] !== void 0 && (o = $) : o === $ ? m[0] === ">" ? (o = r ?? D, _ = -1) : m[1] === void 0 ? _ = -2 : (_ = o.lastIndex - m[2].length, u = m[1], o = m[3] === void 0 ? $ : m[3] === '"' ? yt : ft) : o === yt || o === ft ? o = $ : o === mt || o === gt ? o = D : (o = $, r = void 0);
    const y = o === $ && s[d + 1].startsWith("/>") ? " " : "";
    a += o === D ? l + Ft : _ >= 0 ? (i.push(u), l.slice(0, _) + St + l.slice(_) + v + y) : l + v + (_ === -2 ? d : y);
  }
  return [kt(s, a + (s[e] || "<?>") + (t === 2 ? "</svg>" : t === 3 ? "</math>" : "")), i];
};
class H {
  constructor({ strings: t, _$litType$: e }, i) {
    let r;
    this.parts = [];
    let a = 0, o = 0;
    const d = t.length - 1, l = this.parts, [u, m] = qt(t, e);
    if (this.el = H.createElement(u, i), b.currentNode = this.el.content, e === 2 || e === 3) {
      const _ = this.el.content.firstChild;
      _.replaceWith(..._.childNodes);
    }
    for (; (r = b.nextNode()) !== null && l.length < d; ) {
      if (r.nodeType === 1) {
        if (r.hasAttributes()) for (const _ of r.getAttributeNames()) if (_.endsWith(St)) {
          const f = m[o++], y = r.getAttribute(_).split(v), p = /([.?@])?(.*)/.exec(f);
          l.push({ type: 1, index: a, name: p[2], strings: y, ctor: p[1] === "." ? Gt : p[1] === "?" ? Jt : p[1] === "@" ? Qt : K }), r.removeAttribute(_);
        } else _.startsWith(v) && (l.push({ type: 6, index: a }), r.removeAttribute(_));
        if (zt.test(r.tagName)) {
          const _ = r.textContent.split(v), f = _.length - 1;
          if (f > 0) {
            r.textContent = L ? L.emptyScript : "";
            for (let y = 0; y < f; y++) r.append(_[y], T()), b.nextNode(), l.push({ type: 2, index: ++a });
            r.append(_[f], T());
          }
        }
      } else if (r.nodeType === 8) if (r.data === Et) l.push({ type: 2, index: a });
      else {
        let _ = -1;
        for (; (_ = r.data.indexOf(v, _ + 1)) !== -1; ) l.push({ type: 7, index: a }), _ += v.length - 1;
      }
      a++;
    }
  }
  static createElement(t, e) {
    const i = w.createElement("template");
    return i.innerHTML = t, i;
  }
}
function k(s, t, e = s, i) {
  if (t === z) return t;
  let r = i !== void 0 ? e._$Co?.[i] : e._$Cl;
  const a = P(t) ? void 0 : t._$litDirective$;
  return r?.constructor !== a && (r?._$AO?.(!1), a === void 0 ? r = void 0 : (r = new a(s), r._$AT(s, e, i)), i !== void 0 ? (e._$Co ??= [])[i] = r : e._$Cl = r), r !== void 0 && (t = k(s, r._$AS(s, t.values), r, i)), t;
}
class Kt {
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
    const { el: { content: e }, parts: i } = this._$AD, r = (t?.creationScope ?? w).importNode(e, !0);
    b.currentNode = r;
    let a = b.nextNode(), o = 0, d = 0, l = i[0];
    for (; l !== void 0; ) {
      if (o === l.index) {
        let u;
        l.type === 2 ? u = new R(a, a.nextSibling, this, t) : l.type === 1 ? u = new l.ctor(a, l.name, l.strings, this, t) : l.type === 6 && (u = new Yt(a, this, t)), this._$AV.push(u), l = i[++d];
      }
      o !== l?.index && (a = b.nextNode(), o++);
    }
    return b.currentNode = w, r;
  }
  p(t) {
    let e = 0;
    for (const i of this._$AV) i !== void 0 && (i.strings !== void 0 ? (i._$AI(t, i, e), e += i.strings.length - 2) : i._$AI(t[e])), e++;
  }
}
class R {
  get _$AU() {
    return this._$AM?._$AU ?? this._$Cv;
  }
  constructor(t, e, i, r) {
    this.type = 2, this._$AH = c, this._$AN = void 0, this._$AA = t, this._$AB = e, this._$AM = i, this.options = r, this._$Cv = r?.isConnected ?? !0;
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
    t = k(this, t, e), P(t) ? t === c || t == null || t === "" ? (this._$AH !== c && this._$AR(), this._$AH = c) : t !== this._$AH && t !== z && this._(t) : t._$litType$ !== void 0 ? this.$(t) : t.nodeType !== void 0 ? this.T(t) : Wt(t) ? this.k(t) : this._(t);
  }
  O(t) {
    return this._$AA.parentNode.insertBefore(t, this._$AB);
  }
  T(t) {
    this._$AH !== t && (this._$AR(), this._$AH = this.O(t));
  }
  _(t) {
    this._$AH !== c && P(this._$AH) ? this._$AA.nextSibling.data = t : this.T(w.createTextNode(t)), this._$AH = t;
  }
  $(t) {
    const { values: e, _$litType$: i } = t, r = typeof i == "number" ? this._$AC(t) : (i.el === void 0 && (i.el = H.createElement(kt(i.h, i.h[0]), this.options)), i);
    if (this._$AH?._$AD === r) this._$AH.p(e);
    else {
      const a = new Kt(r, this), o = a.u(this.options);
      a.p(e), this.T(o), this._$AH = a;
    }
  }
  _$AC(t) {
    let e = vt.get(t.strings);
    return e === void 0 && vt.set(t.strings, e = new H(t)), e;
  }
  k(t) {
    ot(this._$AH) || (this._$AH = [], this._$AR());
    const e = this._$AH;
    let i, r = 0;
    for (const a of t) r === e.length ? e.push(i = new R(this.O(T()), this.O(T()), this, this.options)) : i = e[r], i._$AI(a), r++;
    r < e.length && (this._$AR(i && i._$AB.nextSibling, r), e.length = r);
  }
  _$AR(t = this._$AA.nextSibling, e) {
    for (this._$AP?.(!1, !0, e); t !== this._$AB; ) {
      const i = pt(t).nextSibling;
      pt(t).remove(), t = i;
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
  constructor(t, e, i, r, a) {
    this.type = 1, this._$AH = c, this._$AN = void 0, this.element = t, this.name = e, this._$AM = r, this.options = a, i.length > 2 || i[0] !== "" || i[1] !== "" ? (this._$AH = Array(i.length - 1).fill(new String()), this.strings = i) : this._$AH = c;
  }
  _$AI(t, e = this, i, r) {
    const a = this.strings;
    let o = !1;
    if (a === void 0) t = k(this, t, e, 0), o = !P(t) || t !== this._$AH && t !== z, o && (this._$AH = t);
    else {
      const d = t;
      let l, u;
      for (t = a[0], l = 0; l < a.length - 1; l++) u = k(this, d[i + l], e, l), u === z && (u = this._$AH[l]), o ||= !P(u) || u !== this._$AH[l], u === c ? t = c : t !== c && (t += (u ?? "") + a[l + 1]), this._$AH[l] = u;
    }
    o && !r && this.j(t);
  }
  j(t) {
    t === c ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, t ?? "");
  }
}
class Gt extends K {
  constructor() {
    super(...arguments), this.type = 3;
  }
  j(t) {
    this.element[this.name] = t === c ? void 0 : t;
  }
}
class Jt extends K {
  constructor() {
    super(...arguments), this.type = 4;
  }
  j(t) {
    this.element.toggleAttribute(this.name, !!t && t !== c);
  }
}
class Qt extends K {
  constructor(t, e, i, r, a) {
    super(t, e, i, r, a), this.type = 5;
  }
  _$AI(t, e = this) {
    if ((t = k(this, t, e, 0) ?? c) === z) return;
    const i = this._$AH, r = t === c && i !== c || t.capture !== i.capture || t.once !== i.once || t.passive !== i.passive, a = t !== c && (i === c || r);
    r && this.element.removeEventListener(this.name, this, i), a && this.element.addEventListener(this.name, this, t), this._$AH = t;
  }
  handleEvent(t) {
    typeof this._$AH == "function" ? this._$AH.call(this.options?.host ?? this.element, t) : this._$AH.handleEvent(t);
  }
}
class Yt {
  constructor(t, e, i) {
    this.element = t, this.type = 6, this._$AN = void 0, this._$AM = e, this.options = i;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  _$AI(t) {
    k(this, t);
  }
}
const Xt = nt.litHtmlPolyfillSupport;
Xt?.(H, R), (nt.litHtmlVersions ??= []).push("3.3.3");
const te = (s, t, e) => {
  const i = e?.renderBefore ?? t;
  let r = i._$litPart$;
  if (r === void 0) {
    const a = e?.renderBefore ?? null;
    i._$litPart$ = r = new R(t.insertBefore(T(), a), a, void 0, e ?? {});
  }
  return r._$AI(s), r;
};
const lt = globalThis;
class x extends A {
  constructor() {
    super(...arguments), this.renderOptions = { host: this }, this._$Do = void 0;
  }
  createRenderRoot() {
    const t = super.createRenderRoot();
    return this.renderOptions.renderBefore ??= t.firstChild, t;
  }
  update(t) {
    const e = this.render();
    this.hasUpdated || (this.renderOptions.isConnected = this.isConnected), super.update(t), this._$Do = te(e, this.renderRoot, this.renderOptions);
  }
  connectedCallback() {
    super.connectedCallback(), this._$Do?.setConnected(!0);
  }
  disconnectedCallback() {
    super.disconnectedCallback(), this._$Do?.setConnected(!1);
  }
  render() {
    return z;
  }
}
x._$litElement$ = !0, x.finalized = !0, lt.litElementHydrateSupport?.({ LitElement: x });
const ee = lt.litElementPolyfillSupport;
ee?.({ LitElement: x });
(lt.litElementVersions ??= []).push("4.2.2");
const S = "irrigation_manager", ie = /* @__PURE__ */ new Set(["unknown", "unavailable"]);
function $t(s) {
  const { hours: t, minutes: e, seconds: i } = s;
  if (![t, e, i].every(Number.isFinite) || t < 0 || e < 0 || e >= 60 || i < 0 || i >= 60) return;
  const r = t * 3600 + e * 60 + i;
  return Number.isFinite(r) && r > 0 ? r : void 0;
}
function bt(s) {
  const t = Math.floor(s / 3600), e = Math.floor(s % 3600 / 60);
  return { hours: t, minutes: e, seconds: s - t * 3600 - e * 60 };
}
function et(s) {
  const t = Math.floor(s / 3600), e = Math.floor(s % 3600 / 60), i = s - t * 3600 - e * 60, r = i.toFixed(6).replace(/0+$/, "").replace(/\.$/, ""), a = Number.isInteger(i) ? String(i).padStart(2, "0") : `${i < 10 ? "0" : ""}${r}`;
  return `${String(t).padStart(2, "0")}:${String(e).padStart(2, "0")}:${a}`;
}
function Dt(s) {
  return !s || typeof s != "object" || !("response" in s) ? {} : s.response;
}
function B(s) {
  if (s instanceof Error) return s.message;
  if (s && typeof s == "object" && "message" in s) {
    const t = s.message;
    if (typeof t == "string") return t;
  }
  return String(s);
}
const se = {
  status: "status_entity",
  pending: "pending_entity",
  next: "next_entity",
  next_start: "next_start_entity",
  today_consumption: "today_consumption_entity",
  month_consumption: "month_consumption_entity",
  runtime_today: "runtime_today_entity",
  runtime_month: "runtime_month_entity",
  physical_meter: "physical_meter_entity"
}, re = {
  anchor: "zone_entity",
  zone: "zone_entity",
  status: "status_entity",
  water_today: "water_today_entity",
  water_month: "water_month_entity",
  runtime_today: "runtime_today_entity",
  runtime_month: "runtime_month_entity",
  next_irrigation: "next_irrigation_entity"
};
function V(s, t) {
  const e = s?.attributes[t];
  return !e || typeof e != "object" || Array.isArray(e) ? {} : Object.fromEntries(
    Object.entries(e).filter(
      (i) => typeof i[1] == "string" && i[1].includes(".")
    )
  );
}
function Ot(s, t, e) {
  const i = { ...s };
  for (const [r, a] of Object.entries(e)) {
    const d = s[a] || t[r];
    d && Object.assign(i, { [a]: d });
  }
  return i;
}
function Q(s, t) {
  const e = t.entity ? s.states[t.entity] : void 0, i = { ...t };
  return Ot(i, V(e, "card_entities"), se);
}
function Y(s, t) {
  const e = t.entity ? s.states[t.entity] : void 0, i = { ...t }, r = Ot(i, V(e, "card_entities"), re);
  return !r.zone_entity && e && (r.zone_entity = e.entity_id), !r.status_entity && e && (r.status_entity = e.entity_id), r;
}
function G(s, t) {
  if (!s || !s.entity_id.startsWith("sensor.")) return !1;
  const e = s.attributes.config_entry_id;
  if (typeof e != "string" || !e) return !1;
  if (t === "installation")
    return typeof s.attributes.zone_subentry_id == "string" ? !1 : V(s, "card_entities").status === s.entity_id;
  const i = s.attributes.zone_subentry_id;
  if (typeof i != "string" || !i) return !1;
  const r = V(s, "card_entities");
  return r.anchor ? r.anchor === s.entity_id : r.zone === s.entity_id;
}
function ae(s, t) {
  return Object.values(s.states).filter((e) => G(e, t)).map((e) => e.entity_id);
}
function g(s, t) {
  return t ? s.states[t] : void 0;
}
function ne(s) {
  return !!(s && !ie.has(s.state));
}
function E(s, t) {
  const e = s?.attributes[t];
  return typeof e == "string" && e ? e : void 0;
}
function U(s, t) {
  const e = s?.attributes[t];
  return typeof e == "number" && Number.isFinite(e) ? e : void 0;
}
function Ct(s) {
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
  }[s] ?? "mdi:information-outline";
}
function oe(s, t) {
  s.dispatchEvent(
    new CustomEvent("config-changed", {
      detail: { config: t },
      bubbles: !0,
      composed: !0
    })
  );
}
const Nt = {
  en: {
    overview: "Irrigation overview",
    zone: "Irrigation zone",
    unavailable: "Unavailable",
    unknown: "Unknown",
    missing: "Entity not found",
    select_installation: "Select an irrigation installation.",
    select_zone: "Select an irrigation zone.",
    invalid_installation_anchor: "Select the irrigation installation status entity.",
    invalid_zone_anchor: "Select the irrigation zone status entity.",
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
    maximum: "Maximum",
    start: "Start now",
    invalid_target: "Enter a value greater than zero.",
    invalid_duration: "Enter a valid positive duration.",
    hard_limit_required: "Enter a valid positive maximum duration.",
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
    stop_watering: "Stop irrigation",
    confirm_stop_watering: "Stop the active irrigation for this zone?",
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
    runtime: "Runtime",
    water_amount: "Water amount",
    pagination: "History pagination",
    page: "Page",
    of: "of",
    entries: "Entries",
    previous: "Previous",
    next_page: "Next",
    date: "Date",
    today: "Today",
    previous_day: "Previous day",
    next_day: "Next day",
    no_orders_for_day: "No open irrigation orders for this day.",
    next_orders_on: "Show next orders on"
  },
  de: {
    overview: "Bewässerungsübersicht",
    zone: "Bewässerungszone",
    unavailable: "Nicht verfügbar",
    unknown: "Unbekannt",
    missing: "Entity nicht gefunden",
    select_installation: "Bewässerungsanlage auswählen.",
    select_zone: "Bewässerungszone auswählen.",
    invalid_installation_anchor: "Die Status-Entity der Bewässerungsanlage auswählen.",
    invalid_zone_anchor: "Die Status-Entity der Bewässerungszone auswählen.",
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
    maximum: "Maximum",
    start: "Sofort starten",
    invalid_target: "Einen Wert größer als null eingeben.",
    invalid_duration: "Eine gültige positive Dauer eingeben.",
    hard_limit_required: "Eine gültige positive maximale Dauer eingeben.",
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
    stop_watering: "Bewässerung stoppen",
    confirm_stop_watering: "Die laufende Bewässerung dieser Zone wirklich stoppen?",
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
    runtime: "Laufzeit",
    water_amount: "Wassermenge",
    pagination: "Seitennavigation des Bewässerungsverlaufs",
    page: "Seite",
    of: "von",
    entries: "Einträge",
    previous: "Zurück",
    next_page: "Weiter",
    date: "Datum",
    today: "Heute",
    previous_day: "Vorheriger Tag",
    next_day: "Nächster Tag",
    no_orders_for_day: "An diesem Tag sind keine Bewässerungsaufträge offen.",
    next_orders_on: "Nächste Aufträge anzeigen am"
  }
};
function n(s, t) {
  const e = s.language?.toLowerCase().startsWith("de") ? "de" : "en";
  return Nt[e][t];
}
function N(s, t) {
  return t in Nt.en ? n(s, t) : t.replaceAll("_", " ");
}
function M(s, t) {
  if (!t) return n(s, "missing");
  if (t.state === "unavailable") return n(s, "unavailable");
  if (t.state === "unknown" || t.state === "") return n(s, "unknown");
  if (s.formatEntityState) return s.formatEntityState(t);
  const e = t.attributes.unit_of_measurement;
  return `${N(s, t.state)}${e ? ` ${e}` : ""}`;
}
const Mt = wt`
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
  label.field, .field { display: grid; gap: 5px; color: var(--secondary-text-color); font-size: 0.8rem; }
  .field > label { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 6px; }
  .duration-input { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }
  .duration-input label { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 4px; }
  .duration-input label span { min-width: 24px; }
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
  .history-list article span, .history-list article time { color: var(--secondary-text-color); font-size: 0.82rem; }
  .history-period { display: flex; flex-wrap: wrap; gap: 4px; }
  .pagination { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 10px; margin-top: 12px; }
  .pagination-summary { display: grid; gap: 2px; text-align: center; color: var(--secondary-text-color); font-size: 0.78rem; }
  .pagination-summary strong { color: var(--primary-text-color); font-size: 0.88rem; font-weight: 500; }
  .dialog-actions { margin-top: 16px; justify-content: flex-end; }
  .date-navigation { display: grid; grid-template-columns: 40px minmax(160px, 240px) 40px; justify-content: center; align-items: end; gap: 8px; margin-bottom: 14px; }
  .selected-date { margin-bottom: 8px; text-transform: capitalize; }
  .order-list { display: grid; }
  .order-list article { display: grid; gap: 4px; padding: 12px 0; border-bottom: 1px solid var(--divider-color); }
  .order-list article > div { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
  .order-list article span, .order-list time { color: var(--secondary-text-color); font-size: 0.85rem; }
  .empty-day { display: grid; justify-items: start; gap: 8px; }
  .empty-day p { margin-bottom: 0; }
  @container (max-width: 520px) { .table-row { grid-template-columns: 1fr 1fr; } }
  :host { container-type: inline-size; }
  @media (max-width: 480px) {
    .card { padding: 14px; }
    .form-grid { grid-template-columns: 1fr; }
    .actions button { flex: 1 1 calc(50% - 8px); }
    .pagination { grid-template-columns: 1fr 1fr; }
    .pagination-summary { grid-column: 1 / -1; grid-row: 1; }
    .pagination button { width: 100%; }
  }
`, le = wt`
  :host { display: block; }
  .editor { display: grid; gap: 18px; padding: 8px 0; }
  section { display: grid; gap: 10px; }
  h3 { margin: 0; font-size: 1rem; }
  label.selector { display: grid; gap: 5px; color: var(--secondary-text-color); }
  .error { color: var(--error-color); font-size: 0.875rem; }
  label.selector small { line-height: 1.35; }
  .checks { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 6px 12px; }
  .check { display: flex; align-items: center; gap: 8px; min-height: 34px; }
  input[type="checkbox"] { width: 18px; height: 18px; accent-color: var(--primary-color); }
  select { min-height: 40px; padding: 8px; color: var(--primary-text-color); background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 8px; }
`, F = class F extends x {
  setConfig(t) {
    this._config = { ...t };
  }
  updateValue(t, e) {
    const i = { ...this._config, [t]: e };
    (e === void 0 || e === "") && delete i[t], this._config = i, oe(this, i);
  }
  valueChanged(t) {
    const e = t.detail?.value;
    this.updateValue("entity", typeof e == "string" ? e : void 0);
  }
  anchorSelector(t) {
    const e = this._config.entity ? this.hass.states[this._config.entity] : void 0, i = !!(this._config.entity && !G(e, t));
    return h`
      <label class="selector">
        <span>${n(this.hass, t)}</span>
        <ha-selector
          data-testid="anchor-selector"
          .hass=${this.hass}
          .value=${this._config.entity ?? ""}
          .selector=${{
      entity: {
        include_entities: ae(this.hass, t),
        filter: {
          integration: S,
          domain: "sensor",
          device_class: "enum"
        }
      }
    }}
          @value-changed=${this.valueChanged}
        ></ha-selector>
        ${i ? h`<span class="error" role="alert">${n(
      this.hass,
      t === "installation" ? "invalid_installation_anchor" : "invalid_zone_anchor"
    )}</span>` : c}
      </label>
    `;
  }
};
F.styles = le, F.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 }
};
let j = F;
class he extends j {
  render() {
    return !this.hass || !this._config ? c : h`
      <div class="editor">
        <section>${this.anchorSelector("installation")}</section>
      </div>
    `;
  }
}
class ce extends j {
  render() {
    return !this.hass || !this._config ? c : h`
      <div class="editor">
        <section>${this.anchorSelector("zone")}</section>
      </div>
    `;
  }
}
const W = class W extends x {
  constructor() {
    super(...arguments), this._busy = !1, this._ordersOpen = !1, this._orders = [], this._ordersDate = "";
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
    return h`<div class="metric"><span>${t}</span><strong>${M(this.hass, e)}</strong></div>`;
  }
  async call(t, e, i = {}) {
    if (e && !window.confirm(e)) return;
    const r = Q(this.hass, this._config), a = g(this.hass, r.status_entity), o = E(a, "config_entry_id");
    if (!o) {
      this._error = n(this.hass, "configuration_error");
      return;
    }
    this._busy = !0, this._error = void 0;
    try {
      await this.hass.callService(S, t, { config_entry_id: o, ...i });
    } catch (d) {
      this._error = `${n(this.hass, "action_failed")}: ${B(d)}`;
    } finally {
      this._busy = !1;
    }
  }
  async openOrders() {
    const t = Q(this.hass, this._config), e = E(g(this.hass, t.status_entity), "config_entry_id");
    if (e) {
      this._ordersDate = this.dateKey(/* @__PURE__ */ new Date()), this._ordersOpen = !0, this._busy = !0, this._error = void 0;
      try {
        const i = await this.hass.callService(
          S,
          "list_card_orders",
          { config_entry_id: e },
          void 0,
          !1,
          !0
        ), r = Dt(i);
        this._orders = r.orders ?? [];
      } catch (i) {
        this._error = `${n(this.hass, "action_failed")}: ${B(i)}`;
      } finally {
        this._busy = !1;
      }
    }
  }
  target(t) {
    return t.target_type === "volume" ? `${String(t.target_value)} ${n(this.hass, "liters")}` : et(Number(t.target_value));
  }
  dateKey(t) {
    const e = t instanceof Date ? t : new Date(t), i = new Intl.DateTimeFormat("en", {
      timeZone: this.hass.config?.time_zone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit"
    }).formatToParts(e), r = (a) => i.find((o) => o.type === a)?.value ?? "";
    return `${r("year")}-${r("month")}-${r("day")}`;
  }
  shiftOrdersDate(t) {
    const e = /* @__PURE__ */ new Date(`${this._ordersDate}T12:00:00Z`);
    e.setUTCDate(e.getUTCDate() + t), this._ordersDate = e.toISOString().slice(0, 10);
  }
  formatDate(t) {
    const e = new Intl.DateTimeFormat(this.hass.language, {
      timeZone: "UTC",
      weekday: "long",
      year: "numeric",
      month: "2-digit",
      day: "2-digit"
    }).format(/* @__PURE__ */ new Date(`${t}T12:00:00Z`));
    return t === this.dateKey(/* @__PURE__ */ new Date()) ? `${n(this.hass, "today")}, ${e}` : e;
  }
  formatTime(t) {
    return new Intl.DateTimeFormat(this.hass.language, {
      timeZone: this.hass.config?.time_zone,
      hour: "2-digit",
      minute: "2-digit"
    }).format(new Date(String(t)));
  }
  ordersForSelectedDate() {
    return this._orders.filter((t) => this.dateKey(String(t.expected_start)) === this._ordersDate).sort((t, e) => new Date(String(t.expected_start)).getTime() - new Date(String(e.expected_start)).getTime());
  }
  nextOrdersDate() {
    return this._orders.map((t) => this.dateKey(String(t.expected_start))).filter((t) => t > this._ordersDate).sort()[0];
  }
  render() {
    if (!this.hass || !this._config) return c;
    if (!this._config.entity)
      return h`<ha-card><div class="card"><div class="warning" role="alert"><ha-icon icon="mdi:water-outline"></ha-icon><span>${n(this.hass, "select_installation")}</span></div></div></ha-card>`;
    if (!G(g(this.hass, this._config.entity), "installation"))
      return h`<ha-card><div class="card"><div class="warning danger" role="alert"><ha-icon icon="mdi:water-alert"></ha-icon><span>${n(this.hass, "invalid_installation_anchor")}</span></div></div></ha-card>`;
    const t = Q(this.hass, this._config);
    if (!t.status_entity || !g(this.hass, t.status_entity))
      return h`<ha-card><div class="card"><div class="warning"><ha-icon icon="mdi:water-alert"></ha-icon><span>${n(this.hass, "missing")}</span></div></div></ha-card>`;
    const e = g(this.hass, t.status_entity), i = E(e, "config_entry_id"), r = e?.state ?? "unavailable", a = e?.attributes.volume_control_available === !0, o = typeof e?.attributes.card_name == "string" ? e.attributes.card_name : e?.attributes.friendly_name ?? n(this.hass, "overview"), d = this.ordersForSelectedDate(), l = this.nextOrdersDate();
    return h`
      <ha-card>
        <div class="card">
          <header>
            <div class="hero">
              <ha-icon .icon=${Ct(r)}></ha-icon>
              <div>
                <h2>${o}</h2>
                <strong>${ne(e) ? N(this.hass, e.state) : M(this.hass, e)}</strong>
              </div>
            </div>
          </header>

          <div class="metrics">
            <button class="metric metric-button" data-testid="open-orders" ?disabled=${this._busy || !i} @click=${this.openOrders}><span>${n(this.hass, "pending")}</span><strong>${M(this.hass, g(this.hass, t.pending_entity))}</strong></button>
            ${this.metric(n(this.hass, "next_zone"), g(this.hass, t.next_entity))}
            ${this.metric(n(this.hass, "expected_start"), g(this.hass, t.next_start_entity))}
            ${this.metric(n(this.hass, a ? "water_today" : "runtime_today"), g(this.hass, a ? t.today_consumption_entity : t.runtime_today_entity))}
            ${this.metric(n(this.hass, a ? "water_month" : "runtime_month"), g(this.hass, a ? t.month_consumption_entity : t.runtime_month_entity))}
            ${a ? this.metric(n(this.hass, "physical_meter"), g(this.hass, t.physical_meter_entity)) : c}
          </div>

          ${this._error ? h`<div class="error" role="alert">${this._error}</div>` : c}
          <div class="actions">
            <button class="danger emergency" data-testid="emergency-stop" ?disabled=${this._busy || !i} @click=${() => this.call("emergency_stop")}><ha-icon icon="mdi:alert-octagon-outline"></ha-icon>${n(this.hass, "emergency")}</button>
          </div>
          ${this._ordersOpen ? h`
            <dialog open aria-labelledby="orders-title">
              <div class="dialog-header"><h2 id="orders-title">${n(this.hass, "irrigation_orders")}</h2><button class="icon-button" aria-label=${n(this.hass, "close")} @click=${() => {
      this._ordersOpen = !1;
    }}>×</button></div>
              <div class="date-navigation">
                <button class="icon-button" aria-label=${n(this.hass, "previous_day")} @click=${() => this.shiftOrdersDate(-1)}><ha-icon icon="mdi:chevron-left"></ha-icon></button>
                <label class="field"><span>${n(this.hass, "date")}</span><input data-testid="orders-date" type="date" .value=${this._ordersDate} @change=${(u) => {
      const m = u.target;
      this._ordersDate = m.value || this.dateKey(/* @__PURE__ */ new Date()), m.value = this._ordersDate;
    }} /></label>
                <button class="icon-button" aria-label=${n(this.hass, "next_day")} @click=${() => this.shiftOrdersDate(1)}><ha-icon icon="mdi:chevron-right"></ha-icon></button>
              </div>
              <h3 class="selected-date" aria-live="polite">${this.formatDate(this._ordersDate)}</h3>
              ${this._busy ? h`<p aria-live="polite">${n(this.hass, "loading")}</p>` : this._orders.length === 0 ? h`<p>${n(this.hass, "no_open_orders")}</p>` : d.length === 0 ? h`
                <div class="empty-day"><p>${n(this.hass, "no_orders_for_day")}</p>${l ? h`<button data-testid="next-orders-date" @click=${() => {
      this._ordersDate = l;
    }}>${n(this.hass, "next_orders_on")} ${this.formatDate(l)}</button>` : c}</div>` : h`
                <div class="order-list">
                  ${d.map((u) => h`<article><div><strong>${String(u.zone)}</strong><time datetime=${String(u.expected_start)}>${this.formatTime(u.expected_start)}</time></div><span>${N(this.hass, String(u.source))} · ${this.target(u)} · ${N(this.hass, String(u.status))}</span></article>`)}
                </div>`}
            </dialog>` : c}
        </div>
      </ha-card>
    `;
  }
};
W.styles = Mt, W.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 },
  _busy: { state: !0 },
  _error: { state: !0 },
  _ordersOpen: { state: !0 },
  _orders: { state: !0 },
  _ordersDate: { state: !0 }
};
let it = W;
const O = 20;
function X(s, t) {
  return t == null ? "–" : N(s, String(t));
}
const Z = class Z extends x {
  constructor() {
    super(...arguments), this._targetMode = "duration", this._targetValue = 600, this._durationValue = bt(600), this._hardLimit = bt(3600), this._busy = !1, this._manualOpen = !1, this._historyOpen = !1, this._conflictPolicy = "start_now", this._history = [], this._historyOffset = 0, this._historyTotal = 0, this._historySource = "", this._historyResult = "";
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
    return h`<div class="metric"><span>${t}</span><strong>${M(this.hass, e)}</strong></div>`;
  }
  context() {
    const t = Y(this.hass, this._config), e = g(this.hass, t.zone_entity), i = E(e, "config_entry_id"), r = E(e, "zone_subentry_id");
    return i && r ? { config_entry_id: i, zone_subentry_id: r } : void 0;
  }
  async perform(t, e, i, r = !1) {
    if (!(i && !window.confirm(i))) {
      this._busy = !0, this._error = void 0;
      try {
        r ? await this.hass.callService(S, t, e, void 0, !1, !0) : await this.hass.callService(S, t, e);
      } catch (a) {
        this._error = `${n(this.hass, "action_failed")}: ${B(a)}`;
      } finally {
        this._busy = !1;
      }
    }
  }
  async request() {
    const t = this.context();
    if (!t) {
      this._error = n(this.hass, "configuration_error");
      return;
    }
    const e = $t(this._durationValue), i = $t(this._hardLimit);
    if (this._targetMode === "duration" && e === void 0) {
      this._error = n(this.hass, "invalid_duration");
      return;
    }
    if (this._targetMode === "amount" && (!Number.isFinite(this._targetValue) || this._targetValue <= 0)) {
      this._error = n(this.hass, "invalid_target");
      return;
    }
    if (this._targetMode === "amount" && i === void 0) {
      this._error = n(this.hass, "hard_limit_required");
      return;
    }
    const r = g(this.hass, Y(this.hass, this._config).zone_entity), a = this._targetMode === "duration" ? U(r, "max_manual_duration_seconds") : U(r, "max_manual_volume_runtime_seconds"), o = this._targetMode === "duration" ? e : i;
    if (o === void 0) return;
    if (a !== void 0 && o > a) {
      this._error = n(this.hass, "invalid_target");
      return;
    }
    const d = this._targetMode === "duration" ? { duration: e } : { amount: this._targetValue, hard_time_limit: i }, l = r?.attributes.active_execution === !0;
    await this.perform("start_manual_from_card", {
      ...t,
      ...d,
      conflict_policy: l ? this._conflictPolicy : "start_now"
    }, void 0, !0), this._error || (this._manualOpen = !1);
  }
  openManual(t) {
    this._conflictPolicy = t?.attributes.active_execution === !0 ? "stop_active" : "start_now", this._manualOpen = !0, this._error = void 0;
  }
  durationFields(t, e, i, r) {
    const a = (o, d, l) => h`
      <label>
        <input
          data-testid=${`${t}-${o}`}
          type="number"
          min="0"
          max=${l ?? c}
          step="1"
          .value=${String(e[o])}
          @input=${(u) => {
      r({ ...e, [o]: Number(u.target.value) });
    }}
        />
        <span>${d}</span>
      </label>
    `;
    return h`
      <div class="duration-input" title=${`${n(this.hass, "maximum")}: ${et(i)}`}>
        ${a("hours", "h")}
        ${a("minutes", "min", 59)}
        ${a("seconds", "s", 59)}
      </div>
    `;
  }
  async loadHistory(t = 0) {
    const e = this.context();
    if (e) {
      this._historyOpen = !0, this._busy = !0, this._error = void 0;
      try {
        const i = { ...e, offset: t, limit: O };
        this._historySource && (i.source = this._historySource), this._historyResult && (i.result = this._historyResult);
        const r = await this.hass.callService(
          S,
          "list_zone_history",
          i,
          void 0,
          !1,
          !0
        ), a = Dt(r);
        this._history = a.items ?? [], this._historyOffset = a.offset ?? t, this._historyTotal = a.total ?? 0;
      } catch (i) {
        this._error = `${n(this.hass, "action_failed")}: ${B(i)}`;
      } finally {
        this._busy = !1;
      }
    }
  }
  parseNonNegativeNumber(t) {
    if (t == null || t === "") return;
    const e = typeof t == "number" ? t : Number(t);
    return Number.isFinite(e) && e >= 0 ? e : void 0;
  }
  formatHistoryDate(t) {
    if (typeof t != "string" || t === "") return "–";
    const e = new Date(t);
    if (Number.isNaN(e.getTime())) return "–";
    const i = {
      dateStyle: "medium",
      timeStyle: "medium",
      timeZone: this.hass.config?.time_zone
    };
    try {
      return new Intl.DateTimeFormat(this.hass.language || "en", i).format(e);
    } catch {
      return new Intl.DateTimeFormat("en", {
        dateStyle: "medium",
        timeStyle: "medium"
      }).format(e);
    }
  }
  formatHistoryDuration(t) {
    const e = this.parseNonNegativeNumber(t);
    return e === void 0 ? "–" : et(e);
  }
  formatLiters(t) {
    const e = this.parseNonNegativeNumber(t);
    if (e === void 0) return "–";
    const i = {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    };
    let r;
    try {
      r = new Intl.NumberFormat(this.hass.language || "en", i).format(e);
    } catch {
      r = new Intl.NumberFormat("en", i).format(e);
    }
    return `${r} ${n(this.hass, "liters")}`;
  }
  historyTarget(t) {
    return t.target_type === "volume" ? this.formatLiters(t.target_value) : this.formatHistoryDuration(t.target_value);
  }
  render() {
    if (!this.hass || !this._config) return c;
    if (!this._config.entity)
      return h`<ha-card><div class="card"><div class="warning" role="alert"><ha-icon icon="mdi:water-outline"></ha-icon><span>${n(this.hass, "select_zone")}</span></div></div></ha-card>`;
    if (!G(g(this.hass, this._config.entity), "zone"))
      return h`<ha-card><div class="card"><div class="warning danger" role="alert"><ha-icon icon="mdi:water-alert"></ha-icon><span>${n(this.hass, "invalid_zone_anchor")}</span></div></div></ha-card>`;
    const t = Y(this.hass, this._config);
    if (!t.zone_entity || !g(this.hass, t.zone_entity))
      return h`<ha-card><div class="card"><div class="warning"><ha-icon icon="mdi:water-alert"></ha-icon><span>${n(this.hass, "missing")}</span></div></div></ha-card>`;
    const e = g(this.hass, t.zone_entity), i = g(this.hass, t.status_entity), r = this.context(), a = E(e, "active_execution_id"), o = typeof e?.attributes.card_name == "string" ? e.attributes.card_name : e?.attributes.friendly_name ?? n(this.hass, "zone"), d = ["disabled", "installation_disabled", "safety_lock", "needs_reconfiguration"].includes(
      i?.state ?? ""
    ), l = U(e, "max_manual_duration_seconds") ?? 604800, u = U(e, "max_manual_volume_runtime_seconds") ?? 604800, m = this._historyTotal === 0 ? 0 : this._historyOffset + 1, _ = Math.min(this._historyOffset + this._history.length, this._historyTotal), f = Math.floor(this._historyOffset / O) + 1, y = Math.max(1, Math.ceil(this._historyTotal / O));
    return h`
      <ha-card>
        <div class="card">
          <header>
            <div class="hero">
              <ha-icon .icon=${Ct(i?.state ?? "unknown")}></ha-icon>
              <div>
                <h2>${o}</h2>
                <strong>${M(this.hass, i)}</strong>
              </div>
            </div>
          </header>

          <div class="metrics">
            ${this.metric(n(this.hass, "status"), i)}
            ${this.metric(n(this.hass, e?.attributes.volume_control_available === !0 ? "water_today" : "runtime_today"), g(this.hass, e?.attributes.volume_control_available === !0 ? t.water_today_entity : t.runtime_today_entity))}
            ${this.metric(n(this.hass, e?.attributes.volume_control_available === !0 ? "water_month" : "runtime_month"), g(this.hass, e?.attributes.volume_control_available === !0 ? t.water_month_entity : t.runtime_month_entity))}
            ${this.metric(n(this.hass, "next"), g(this.hass, t.next_irrigation_entity))}
          </div>

          ${this._error ? h`<div class="error" role="alert">${this._error}</div>` : c}
          <div class="actions">
            <button class="primary" data-testid="manual-irrigation" ?disabled=${this._busy || d || !r} @click=${() => this.openManual(e)}><ha-icon icon="mdi:sprinkler-variant"></ha-icon>${n(this.hass, "manual_water")}</button>
            ${i?.state === "watering" && a && r ? h`<button class="danger" data-testid="stop-watering" ?disabled=${this._busy} @click=${() => this.perform("stop", { config_entry_id: r.config_entry_id, execution_id: a }, n(this.hass, "confirm_stop_watering"))}><ha-icon icon="mdi:stop-circle-outline"></ha-icon>${n(this.hass, "stop_watering")}</button>` : c}
            <button data-testid="show-history" ?disabled=${this._busy || !r} @click=${() => this.loadHistory(0)}><ha-icon icon="mdi:history"></ha-icon>${n(this.hass, "show_history")}</button>
          </div>
          ${this._manualOpen ? h`
            <dialog open aria-labelledby="manual-title">
              <div class="dialog-header"><h2 id="manual-title">${n(this.hass, "manual_water")}</h2><button class="icon-button" aria-label=${n(this.hass, "close")} @click=${() => {
      this._manualOpen = !1;
    }}>×</button></div>
              <div class="form-grid">
                <label class="field"><span>${n(this.hass, "target")}</span><select data-testid="target-mode" .value=${this._targetMode} @change=${(p) => {
      this._targetMode = p.target.value;
    }}><option value="duration">${n(this.hass, "duration_mode")}</option>${e?.attributes.volume_control_available === !0 ? h`<option value="amount">${n(this.hass, "amount_mode")}</option>` : c}</select></label>
                 <div class="field"><span>${this._targetMode === "duration" ? n(this.hass, "duration") : n(this.hass, "amount")}</span>${this._targetMode === "duration" ? this.durationFields("manual-target", this._durationValue, l, (p) => {
      this._durationValue = p;
    }) : h`<label><input data-testid="manual-target" type="number" min="0.001" max="1000000" step="0.1" .value=${String(this._targetValue)} @input=${(p) => {
      this._targetValue = Number(p.target.value);
    }} /><span>${n(this.hass, "liters")}</span></label>`}</div>
                 ${this._targetMode === "amount" ? h`<div class="field"><span>${n(this.hass, "hard_limit")}</span>${this.durationFields("hard-limit", this._hardLimit, u, (p) => {
      this._hardLimit = p;
    })}</div>` : c}
                ${e?.attributes.active_execution === !0 ? h`<label class="field"><span>${n(this.hass, "active_execution_choice")}</span><select data-testid="conflict-policy" .value=${this._conflictPolicy} @change=${(p) => {
      this._conflictPolicy = p.target.value;
    }}><option value="stop_active">${n(this.hass, "stop_active_start_now")}</option><option value="priority_next">${n(this.hass, "finish_then_priority")}</option></select></label>` : c}
              </div>
              ${this._error ? h`<div class="error" role="alert">${this._error}</div>` : c}
              <div class="actions dialog-actions"><button data-testid="submit-manual" class="primary" ?disabled=${this._busy} @click=${this.request}>${n(this.hass, "start")}</button></div>
            </dialog>` : c}
          ${this._historyOpen ? h`
            <dialog open aria-labelledby="history-title">
              <div class="dialog-header"><h2 id="history-title">${n(this.hass, "irrigation_history")}</h2><button class="icon-button" aria-label=${n(this.hass, "close")} @click=${() => {
      this._historyOpen = !1;
    }}>×</button></div>
              <div class="filters"><label class="field"><span>${n(this.hass, "source")}</span><select .value=${this._historySource} @change=${(p) => {
      this._historySource = p.target.value, this.loadHistory(0);
    }}><option value="">${n(this.hass, "all")}</option><option value="manual">${n(this.hass, "manual")}</option><option value="automatic">${n(this.hass, "automatic")}</option></select></label><label class="field"><span>${n(this.hass, "result")}</span><select .value=${this._historyResult} @change=${(p) => {
      this._historyResult = p.target.value, this.loadHistory(0);
    }}><option value="">${n(this.hass, "all")}</option><option value="completed">${n(this.hass, "completed")}</option><option value="failed">${n(this.hass, "failed")}</option><option value="cancelled">${n(this.hass, "cancelled")}</option></select></label></div>
              ${this._busy ? h`<p aria-live="polite">${n(this.hass, "loading")}</p>` : h`
                <div class="history-list">
                  ${this._history.map((p) => h`
                    <article>
                      <strong>${n(this.hass, "target")}: ${this.historyTarget(p)}</strong>
                      <span class="history-period">
                        <time datetime=${String(p.started_at ?? "")}>${this.formatHistoryDate(p.started_at)}</time>
                        <span aria-hidden="true">–</span>
                        <time datetime=${String(p.ended_at ?? "")}>${this.formatHistoryDate(p.ended_at)}</time>
                      </span>
                      <span>
                        ${X(this.hass, p.source)} ·
                        ${X(this.hass, p.result)} ·
                        ${n(this.hass, "runtime")}: ${this.formatHistoryDuration(p.actual_duration)}
                        ${p.actual_water == null ? c : h` · ${n(this.hass, "water_amount")}: ${this.formatLiters(p.actual_water)}`}
                        · ${X(this.hass, p.completion_reason)}
                      </span>
                    </article>
                  `)}
                </div>
              `}
              <nav class="pagination" aria-label=${n(this.hass, "pagination")}>
                <button ?disabled=${this._busy || this._historyOffset === 0} @click=${() => this.loadHistory(Math.max(0, this._historyOffset - O))}>${n(this.hass, "previous")}</button>
                <span class="pagination-summary" aria-live="polite">
                  <strong>${n(this.hass, "page")} ${f} ${n(this.hass, "of")} ${y}</strong>
                  <span>${this._historyTotal === 0 ? `0 ${n(this.hass, "entries")}` : `${n(this.hass, "entries")} ${m}–${_} ${n(this.hass, "of")} ${this._historyTotal}`}</span>
                </span>
                <button ?disabled=${this._busy || this._historyOffset + this._history.length >= this._historyTotal} @click=${() => this.loadHistory(this._historyOffset + O)}>${n(this.hass, "next_page")}</button>
              </nav>
            </dialog>` : c}
        </div>
      </ha-card>
    `;
  }
};
Z.styles = Mt, Z.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 },
  _targetMode: { state: !0 },
  _targetValue: { state: !0 },
  _durationValue: { state: !0 },
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
let st = Z;
const de = [
  ["irrigation-manager-overview-card", it],
  ["irrigation-manager-zone-card", st],
  ["irrigation-manager-overview-card-editor", he],
  ["irrigation-manager-zone-card-editor", ce]
];
for (const [s, t] of de)
  customElements.get(s) || customElements.define(s, t);
window.customCards = window.customCards ?? [];
for (const s of [
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
  window.customCards.some((t) => t.type === s.type) || window.customCards.push(s);
