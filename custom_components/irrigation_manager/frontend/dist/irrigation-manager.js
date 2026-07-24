const B = globalThis, dt = B.ShadowRoot && (B.ShadyCSS === void 0 || B.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype, ut = /* @__PURE__ */ Symbol(), wt = /* @__PURE__ */ new WeakMap();
let Pt = class {
  constructor(t, e, i) {
    if (this._$cssResult$ = !0, i !== ut) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
    this.cssText = t, this.t = e;
  }
  get styleSheet() {
    let t = this.o;
    const e = this.t;
    if (dt && t === void 0) {
      const i = e !== void 0 && e.length === 1;
      i && (t = wt.get(e)), t === void 0 && ((this.o = t = new CSSStyleSheet()).replaceSync(this.cssText), i && wt.set(e, t));
    }
    return t;
  }
  toString() {
    return this.cssText;
  }
};
const Xt = (n) => new Pt(typeof n == "string" ? n : n + "", void 0, ut), Dt = (n, ...t) => {
  const e = n.length === 1 ? n[0] : t.reduce((i, s, o) => i + ((r) => {
    if (r._$cssResult$ === !0) return r.cssText;
    if (typeof r == "number") return r;
    throw Error("Value passed to 'css' function must be a 'css' function result: " + r + ". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.");
  })(s) + n[o + 1], n[0]);
  return new Pt(e, n, ut);
}, te = (n, t) => {
  if (dt) n.adoptedStyleSheets = t.map((e) => e instanceof CSSStyleSheet ? e : e.styleSheet);
  else for (const e of t) {
    const i = document.createElement("style"), s = B.litNonce;
    s !== void 0 && i.setAttribute("nonce", s), i.textContent = e.cssText, n.appendChild(i);
  }
}, xt = dt ? (n) => n : (n) => n instanceof CSSStyleSheet ? ((t) => {
  let e = "";
  for (const i of t.cssRules) e += i.cssText;
  return Xt(e);
})(n) : n;
const { is: ee, defineProperty: ie, getOwnPropertyDescriptor: se, getOwnPropertyNames: ne, getOwnPropertySymbols: ae, getPrototypeOf: oe } = Object, J = globalThis, At = J.trustedTypes, re = At ? At.emptyScript : "", ce = J.reactiveElementPolyfillSupport, R = (n, t) => n, nt = { toAttribute(n, t) {
  switch (t) {
    case Boolean:
      n = n ? re : null;
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
} }, It = (n, t) => !ee(n, t), kt = { attribute: !0, type: String, converter: nt, reflect: !1, useDefault: !1, hasChanged: It };
Symbol.metadata ??= /* @__PURE__ */ Symbol("metadata"), J.litPropertyMetadata ??= /* @__PURE__ */ new WeakMap();
let M = class extends HTMLElement {
  static addInitializer(t) {
    this._$Ei(), (this.l ??= []).push(t);
  }
  static get observedAttributes() {
    return this.finalize(), this._$Eh && [...this._$Eh.keys()];
  }
  static createProperty(t, e = kt) {
    if (e.state && (e.attribute = !1), this._$Ei(), this.prototype.hasOwnProperty(t) && ((e = Object.create(e)).wrapped = !0), this.elementProperties.set(t, e), !e.noAccessor) {
      const i = /* @__PURE__ */ Symbol(), s = this.getPropertyDescriptor(t, i, e);
      s !== void 0 && ie(this.prototype, t, s);
    }
  }
  static getPropertyDescriptor(t, e, i) {
    const { get: s, set: o } = se(this.prototype, t) ?? { get() {
      return this[e];
    }, set(r) {
      this[e] = r;
    } };
    return { get: s, set(r) {
      const u = s?.call(this);
      o?.call(this, r), this.requestUpdate(t, u, i);
    }, configurable: !0, enumerable: !0 };
  }
  static getPropertyOptions(t) {
    return this.elementProperties.get(t) ?? kt;
  }
  static _$Ei() {
    if (this.hasOwnProperty(R("elementProperties"))) return;
    const t = oe(this);
    t.finalize(), t.l !== void 0 && (this.l = [...t.l]), this.elementProperties = new Map(t.elementProperties);
  }
  static finalize() {
    if (this.hasOwnProperty(R("finalized"))) return;
    if (this.finalized = !0, this._$Ei(), this.hasOwnProperty(R("properties"))) {
      const e = this.properties, i = [...ne(e), ...ae(e)];
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
      for (const s of i) e.unshift(xt(s));
    } else t !== void 0 && e.push(xt(t));
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
    return te(t, this.constructor.elementStyles), t;
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
      const o = (i.converter?.toAttribute !== void 0 ? i.converter : nt).toAttribute(e, i.type);
      this._$Em = t, o == null ? this.removeAttribute(s) : this.setAttribute(s, o), this._$Em = null;
    }
  }
  _$AK(t, e) {
    const i = this.constructor, s = i._$Eh.get(t);
    if (s !== void 0 && this._$Em !== s) {
      const o = i.getPropertyOptions(s), r = typeof o.converter == "function" ? { fromAttribute: o.converter } : o.converter?.fromAttribute !== void 0 ? o.converter : nt;
      this._$Em = s;
      const u = r.fromAttribute(e, o.type);
      this[s] = u ?? this._$Ej?.get(s) ?? u, this._$Em = null;
    }
  }
  requestUpdate(t, e, i, s = !1, o) {
    if (t !== void 0) {
      const r = this.constructor;
      if (s === !1 && (o = this[t]), i ??= r.getPropertyOptions(t), !((i.hasChanged ?? It)(o, e) || i.useDefault && i.reflect && o === this._$Ej?.get(t) && !this.hasAttribute(r._$Eu(t, i)))) return;
      this.C(t, e, i);
    }
    this.isUpdatePending === !1 && (this._$ES = this._$EP());
  }
  C(t, e, { useDefault: i, reflect: s, wrapped: o }, r) {
    i && !(this._$Ej ??= /* @__PURE__ */ new Map()).has(t) && (this._$Ej.set(t, r ?? e ?? this[t]), o !== !0 || r !== void 0) || (this._$AL.has(t) || (this.hasUpdated || i || (e = void 0), this._$AL.set(t, e)), s === !0 && this._$Em !== t && (this._$Eq ??= /* @__PURE__ */ new Set()).add(t));
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
        for (const [s, o] of this._$Ep) this[s] = o;
        this._$Ep = void 0;
      }
      const i = this.constructor.elementProperties;
      if (i.size > 0) for (const [s, o] of i) {
        const { wrapped: r } = o, u = this[s];
        r !== !0 || this._$AL.has(s) || u === void 0 || this.C(s, void 0, o, u);
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
M.elementStyles = [], M.shadowRootOptions = { mode: "open" }, M[R("elementProperties")] = /* @__PURE__ */ new Map(), M[R("finalized")] = /* @__PURE__ */ new Map(), ce?.({ ReactiveElement: M }), (J.reactiveElementVersions ??= []).push("2.1.2");
const _t = globalThis, St = (n) => n, V = _t.trustedTypes, Et = V ? V.createPolicy("lit-html", { createHTML: (n) => n }) : void 0, Ut = "$lit$", A = `lit$${Math.random().toFixed(9).slice(2)}$`, Ht = "?" + A, le = `<${Ht}>`, z = document, D = () => z.createComment(""), I = (n) => n === null || typeof n != "object" && typeof n != "function", pt = Array.isArray, he = (n) => pt(n) || typeof n?.[Symbol.iterator] == "function", X = `[\x20\t\n\f\r]`, N = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g, zt = /-->/g, Mt = />/g, k = RegExp(`>|${X}(?:([^\\s"'>=/]+)(${X}*=${X}*(?:[^\x20\t\n\f\r"'\`<>=]|("|')|))|$)`, "g"), Ct = /'/g, Ot = /"/g, Lt = /^(?:script|style|textarea|title)$/i, de = (n) => (t, ...e) => ({ _$litType$: n, strings: t, values: e }), c = de(1), O = /* @__PURE__ */ Symbol.for("lit-noChange"), l = /* @__PURE__ */ Symbol.for("lit-nothing"), qt = /* @__PURE__ */ new WeakMap(), S = z.createTreeWalker(z, 129);
function Bt(n, t) {
  if (!pt(n) || !n.hasOwnProperty("raw")) throw Error("invalid template strings array");
  return Et !== void 0 ? Et.createHTML(t) : t;
}
const ue = (n, t) => {
  const e = n.length - 1, i = [];
  let s, o = t === 2 ? "<svg>" : t === 3 ? "<math>" : "", r = N;
  for (let u = 0; u < e; u++) {
    const d = n[u];
    let p, y, _ = -1, v = 0;
    for (; v < d.length && (r.lastIndex = v, y = r.exec(d), y !== null); ) v = r.lastIndex, r === N ? y[1] === "!--" ? r = zt : y[1] !== void 0 ? r = Mt : y[2] !== void 0 ? (Lt.test(y[2]) && (s = RegExp("</" + y[2], "g")), r = k) : y[3] !== void 0 && (r = k) : r === k ? y[0] === ">" ? (r = s ?? N, _ = -1) : y[1] === void 0 ? _ = -2 : (_ = r.lastIndex - y[2].length, p = y[1], r = y[3] === void 0 ? k : y[3] === '"' ? Ot : Ct) : r === Ot || r === Ct ? r = k : r === zt || r === Mt ? r = N : (r = k, s = void 0);
    const $ = r === k && n[u + 1].startsWith("/>") ? " " : "";
    o += r === N ? d + le : _ >= 0 ? (i.push(p), d.slice(0, _) + Ut + d.slice(_) + A + $) : d + A + (_ === -2 ? u : $);
  }
  return [Bt(n, o + (n[e] || "<?>") + (t === 2 ? "</svg>" : t === 3 ? "</math>" : "")), i];
};
class U {
  constructor({ strings: t, _$litType$: e }, i) {
    let s;
    this.parts = [];
    let o = 0, r = 0;
    const u = t.length - 1, d = this.parts, [p, y] = ue(t, e);
    if (this.el = U.createElement(p, i), S.currentNode = this.el.content, e === 2 || e === 3) {
      const _ = this.el.content.firstChild;
      _.replaceWith(..._.childNodes);
    }
    for (; (s = S.nextNode()) !== null && d.length < u; ) {
      if (s.nodeType === 1) {
        if (s.hasAttributes()) for (const _ of s.getAttributeNames()) if (_.endsWith(Ut)) {
          const v = y[r++], $ = s.getAttribute(_).split(A), m = /([.?@])?(.*)/.exec(v);
          d.push({ type: 1, index: o, name: m[2], strings: $, ctor: m[1] === "." ? pe : m[1] === "?" ? me : m[1] === "@" ? ge : Q }), s.removeAttribute(_);
        } else _.startsWith(A) && (d.push({ type: 6, index: o }), s.removeAttribute(_));
        if (Lt.test(s.tagName)) {
          const _ = s.textContent.split(A), v = _.length - 1;
          if (v > 0) {
            s.textContent = V ? V.emptyScript : "";
            for (let $ = 0; $ < v; $++) s.append(_[$], D()), S.nextNode(), d.push({ type: 2, index: ++o });
            s.append(_[v], D());
          }
        }
      } else if (s.nodeType === 8) if (s.data === Ht) d.push({ type: 2, index: o });
      else {
        let _ = -1;
        for (; (_ = s.data.indexOf(A, _ + 1)) !== -1; ) d.push({ type: 7, index: o }), _ += A.length - 1;
      }
      o++;
    }
  }
  static createElement(t, e) {
    const i = z.createElement("template");
    return i.innerHTML = t, i;
  }
}
function q(n, t, e = n, i) {
  if (t === O) return t;
  let s = i !== void 0 ? e._$Co?.[i] : e._$Cl;
  const o = I(t) ? void 0 : t._$litDirective$;
  return s?.constructor !== o && (s?._$AO?.(!1), o === void 0 ? s = void 0 : (s = new o(n), s._$AT(n, e, i)), i !== void 0 ? (e._$Co ??= [])[i] = s : e._$Cl = s), s !== void 0 && (t = q(n, s._$AS(n, t.values), s, i)), t;
}
class _e {
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
    const { el: { content: e }, parts: i } = this._$AD, s = (t?.creationScope ?? z).importNode(e, !0);
    S.currentNode = s;
    let o = S.nextNode(), r = 0, u = 0, d = i[0];
    for (; d !== void 0; ) {
      if (r === d.index) {
        let p;
        d.type === 2 ? p = new L(o, o.nextSibling, this, t) : d.type === 1 ? p = new d.ctor(o, d.name, d.strings, this, t) : d.type === 6 && (p = new ye(o, this, t)), this._$AV.push(p), d = i[++u];
      }
      r !== d?.index && (o = S.nextNode(), r++);
    }
    return S.currentNode = z, s;
  }
  p(t) {
    let e = 0;
    for (const i of this._$AV) i !== void 0 && (i.strings !== void 0 ? (i._$AI(t, i, e), e += i.strings.length - 2) : i._$AI(t[e])), e++;
  }
}
class L {
  get _$AU() {
    return this._$AM?._$AU ?? this._$Cv;
  }
  constructor(t, e, i, s) {
    this.type = 2, this._$AH = l, this._$AN = void 0, this._$AA = t, this._$AB = e, this._$AM = i, this.options = s, this._$Cv = s?.isConnected ?? !0;
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
    t = q(this, t, e), I(t) ? t === l || t == null || t === "" ? (this._$AH !== l && this._$AR(), this._$AH = l) : t !== this._$AH && t !== O && this._(t) : t._$litType$ !== void 0 ? this.$(t) : t.nodeType !== void 0 ? this.T(t) : he(t) ? this.k(t) : this._(t);
  }
  O(t) {
    return this._$AA.parentNode.insertBefore(t, this._$AB);
  }
  T(t) {
    this._$AH !== t && (this._$AR(), this._$AH = this.O(t));
  }
  _(t) {
    this._$AH !== l && I(this._$AH) ? this._$AA.nextSibling.data = t : this.T(z.createTextNode(t)), this._$AH = t;
  }
  $(t) {
    const { values: e, _$litType$: i } = t, s = typeof i == "number" ? this._$AC(t) : (i.el === void 0 && (i.el = U.createElement(Bt(i.h, i.h[0]), this.options)), i);
    if (this._$AH?._$AD === s) this._$AH.p(e);
    else {
      const o = new _e(s, this), r = o.u(this.options);
      o.p(e), this.T(r), this._$AH = o;
    }
  }
  _$AC(t) {
    let e = qt.get(t.strings);
    return e === void 0 && qt.set(t.strings, e = new U(t)), e;
  }
  k(t) {
    pt(this._$AH) || (this._$AH = [], this._$AR());
    const e = this._$AH;
    let i, s = 0;
    for (const o of t) s === e.length ? e.push(i = new L(this.O(D()), this.O(D()), this, this.options)) : i = e[s], i._$AI(o), s++;
    s < e.length && (this._$AR(i && i._$AB.nextSibling, s), e.length = s);
  }
  _$AR(t = this._$AA.nextSibling, e) {
    for (this._$AP?.(!1, !0, e); t !== this._$AB; ) {
      const i = St(t).nextSibling;
      St(t).remove(), t = i;
    }
  }
  setConnected(t) {
    this._$AM === void 0 && (this._$Cv = t, this._$AP?.(t));
  }
}
class Q {
  get tagName() {
    return this.element.tagName;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  constructor(t, e, i, s, o) {
    this.type = 1, this._$AH = l, this._$AN = void 0, this.element = t, this.name = e, this._$AM = s, this.options = o, i.length > 2 || i[0] !== "" || i[1] !== "" ? (this._$AH = Array(i.length - 1).fill(new String()), this.strings = i) : this._$AH = l;
  }
  _$AI(t, e = this, i, s) {
    const o = this.strings;
    let r = !1;
    if (o === void 0) t = q(this, t, e, 0), r = !I(t) || t !== this._$AH && t !== O, r && (this._$AH = t);
    else {
      const u = t;
      let d, p;
      for (t = o[0], d = 0; d < o.length - 1; d++) p = q(this, u[i + d], e, d), p === O && (p = this._$AH[d]), r ||= !I(p) || p !== this._$AH[d], p === l ? t = l : t !== l && (t += (p ?? "") + o[d + 1]), this._$AH[d] = p;
    }
    r && !s && this.j(t);
  }
  j(t) {
    t === l ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, t ?? "");
  }
}
class pe extends Q {
  constructor() {
    super(...arguments), this.type = 3;
  }
  j(t) {
    this.element[this.name] = t === l ? void 0 : t;
  }
}
class me extends Q {
  constructor() {
    super(...arguments), this.type = 4;
  }
  j(t) {
    this.element.toggleAttribute(this.name, !!t && t !== l);
  }
}
class ge extends Q {
  constructor(t, e, i, s, o) {
    super(t, e, i, s, o), this.type = 5;
  }
  _$AI(t, e = this) {
    if ((t = q(this, t, e, 0) ?? l) === O) return;
    const i = this._$AH, s = t === l && i !== l || t.capture !== i.capture || t.once !== i.once || t.passive !== i.passive, o = t !== l && (i === l || s);
    s && this.element.removeEventListener(this.name, this, i), o && this.element.addEventListener(this.name, this, t), this._$AH = t;
  }
  handleEvent(t) {
    typeof this._$AH == "function" ? this._$AH.call(this.options?.host ?? this.element, t) : this._$AH.handleEvent(t);
  }
}
class ye {
  constructor(t, e, i) {
    this.element = t, this.type = 6, this._$AN = void 0, this._$AM = e, this.options = i;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  _$AI(t) {
    q(this, t);
  }
}
const fe = _t.litHtmlPolyfillSupport;
fe?.(U, L), (_t.litHtmlVersions ??= []).push("3.3.3");
const ve = (n, t, e) => {
  const i = e?.renderBefore ?? t;
  let s = i._$litPart$;
  if (s === void 0) {
    const o = e?.renderBefore ?? null;
    i._$litPart$ = s = new L(t.insertBefore(D(), o), o, void 0, e ?? {});
  }
  return s._$AI(n), s;
};
const mt = globalThis;
class E extends M {
  constructor() {
    super(...arguments), this.renderOptions = { host: this }, this._$Do = void 0;
  }
  createRenderRoot() {
    const t = super.createRenderRoot();
    return this.renderOptions.renderBefore ??= t.firstChild, t;
  }
  update(t) {
    const e = this.render();
    this.hasUpdated || (this.renderOptions.isConnected = this.isConnected), super.update(t), this._$Do = ve(e, this.renderRoot, this.renderOptions);
  }
  connectedCallback() {
    super.connectedCallback(), this._$Do?.setConnected(!0);
  }
  disconnectedCallback() {
    super.disconnectedCallback(), this._$Do?.setConnected(!1);
  }
  render() {
    return O;
  }
}
E._$litElement$ = !0, E.finalized = !0, mt.litElementHydrateSupport?.({ LitElement: E });
const $e = mt.litElementPolyfillSupport;
$e?.({ LitElement: E });
(mt.litElementVersions ??= []).push("4.2.2");
const W = "irrigation_manager", be = /* @__PURE__ */ new Set(["unknown", "unavailable"]), we = {
  status: "status_entity",
  emergency: "emergency_entity",
  lock: "lock_entity",
  active_zone: "active_zone_entity",
  dose: "dose_entity",
  pending: "pending_entity",
  next: "next_entity",
  next_start: "next_start_entity",
  today_consumption: "today_consumption_entity",
  month_consumption: "month_consumption_entity",
  runtime_today: "runtime_today_entity",
  runtime_month: "runtime_month_entity",
  physical_meter: "physical_meter_entity",
  model_quality: "model_quality_entity",
  winter: "winter_entity",
  maintenance: "maintenance_entity",
  automation_release: "automation_release_entity",
  maintenance_due: "maintenance_due_entity"
}, xe = {
  anchor: "zone_entity",
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
  calculation: "calculation_entity",
  water_today: "water_today_entity",
  water_month: "water_month_entity",
  runtime_today: "runtime_today_entity",
  runtime_month: "runtime_month_entity",
  next_irrigation: "next_irrigation_entity"
}, Ae = {
  active_zone: "active_zone_entity",
  dose: "request_entity",
  lock: "installation_safety_lock_entity"
};
function H(n, t) {
  const e = n?.attributes[t];
  return !e || typeof e != "object" || Array.isArray(e) ? {} : Object.fromEntries(
    Object.entries(e).filter(
      (i) => typeof i[1] == "string" && i[1].includes(".")
    )
  );
}
function at(n, t, e) {
  const i = { ...n };
  for (const [s, o] of Object.entries(e)) {
    const u = n[o] || t[s];
    u && Object.assign(i, { [o]: u });
  }
  return i;
}
function tt(n, t) {
  if (!t.configuration_mode && !t.installation && t.status_entity) return t;
  const e = t.installation ? Vt(n, "installation", t.installation) : h(n, t.status_entity);
  return at(t, H(e, "card_entities"), we);
}
function T(n, t) {
  if (!t.configuration_mode && !t.zone && t.zone_entity) return t;
  const e = t.zone ? Vt(n, "zone", t.zone) : h(n, t.zone_entity);
  let i = at(t, H(e, "card_entities"), xe);
  return i = at(
    i,
    H(e, "installation_card_entities"),
    Ae
  ), !i.zone_entity && e && (i.zone_entity = e.entity_id), i;
}
function Vt(n, t, e) {
  return Object.values(n.states).find((i) => ot(i, t) === e);
}
function ot(n, t) {
  const e = n.attributes.config_entry_id;
  if (typeof e != "string") return;
  if (t === "installation")
    return H(n, "card_entities").status === n.entity_id ? e : void 0;
  const i = n.attributes.zone_subentry_id;
  if (typeof i != "string") return;
  const s = H(n, "card_entities");
  return (s.anchor ? s.anchor === n.entity_id : s.zone === n.entity_id) ? `${e}:${i}` : void 0;
}
function gt(n, t) {
  return n.configuration_mode ? n.configuration_mode : t.some((e) => !!n[e]) ? "expert" : "simple";
}
function ke(n, t) {
  return Object.values(n.states).filter((e) => ot(e, t) !== void 0).map((e) => ({
    value: ot(e, t),
    label: typeof e.attributes.card_name == "string" && e.attributes.card_name || e.attributes.friendly_name || e.entity_id
  })).sort((e, i) => e.label.localeCompare(i.label, n.language));
}
function h(n, t) {
  return t ? n.states[t] : void 0;
}
function F(n) {
  return !!(n && !be.has(n.state));
}
function f(n, t) {
  const e = n?.attributes[t];
  return typeof e == "string" && e ? e : void 0;
}
function C(n, t) {
  const e = n?.attributes[t];
  return typeof e == "number" && Number.isFinite(e) ? e : void 0;
}
function et(n, t) {
  if (!t || f(n, "zone_subentry_id") !== t)
    return;
  const e = f(n, "request_id"), i = f(n, "execution_id");
  return e || i ? { requestId: e, executionId: i } : void 0;
}
function Wt(n) {
  const t = C(n, "target_value"), e = C(n, "remaining_value");
  if (!(t === void 0 || e === void 0 || t <= 0))
    return Math.max(0, Math.min(100, (t - e) / t * 100));
}
function Ft(n) {
  return {
    idle: "mdi:water-check-outline",
    watering: "mdi:sprinkler-variant",
    soaking: "mdi:timer-sand",
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
  }[n] ?? "mdi:information-outline";
}
function Se(n, t) {
  n.dispatchEvent(
    new CustomEvent("config-changed", {
      detail: { config: t },
      bubbles: !0,
      composed: !0
    })
  );
}
const Zt = {
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
    needs_reconfiguration: "Reconfiguration required",
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
    installation: "Irrigation installation",
    next_zone: "Next zone",
    expected_start: "Expected start",
    runtime_today: "Runtime today",
    runtime_month: "Runtime this month",
    water_today: "Measured water today",
    water_month: "Measured water this month",
    corrected_meter: "Corrected meter total",
    irrigation_orders: "Irrigation orders",
    no_open_orders: "No open irrigation orders",
    close: "Close",
    loading: "Loading…",
    manual_water: "Water manually",
    show_history: "Show history",
    active_execution_choice: "Another irrigation execution is active",
    stop_active_start_now: "Stop active execution and start now",
    finish_then_priority: "Finish active execution and run next",
    irrigation_history: "Irrigation history",
    source: "Source",
    result: "Result",
    all: "All",
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
    soaking: "Sickerpause",
    error: "Fehler",
    safety_lock: "Sicherheitssperre",
    needs_reconfiguration: "Neukonfiguration erforderlich",
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
    installation: "Bewässerungsanlage",
    next_zone: "Nächste Zone",
    expected_start: "Erwarteter Start",
    runtime_today: "Laufzeit heute",
    runtime_month: "Laufzeit diesen Monat",
    water_today: "Gemessenes Wasser heute",
    water_month: "Gemessenes Wasser diesen Monat",
    corrected_meter: "Abgeglichener Zählerstand",
    irrigation_orders: "Bewässerungsaufträge",
    no_open_orders: "Keine offenen Bewässerungsaufträge",
    close: "Schließen",
    loading: "Wird geladen…",
    manual_water: "Manuell bewässern",
    show_history: "Verlauf anzeigen",
    active_execution_choice: "Ein anderer Bewässerungsvorgang ist aktiv",
    stop_active_start_now: "Aktiven Vorgang beenden und sofort starten",
    finish_then_priority: "Aktiven Vorgang abschließen und danach ausführen",
    irrigation_history: "Bewässerungsverlauf",
    source: "Quelle",
    result: "Ergebnis",
    all: "Alle",
    automatic: "Automatisch",
    completed: "Abgeschlossen",
    failed: "Fehlgeschlagen",
    cancelled: "Abgebrochen",
    previous: "Zurück",
    next_page: "Weiter"
  }
};
function a(n, t) {
  const e = n.language?.toLowerCase().startsWith("de") ? "de" : "en";
  return Zt[e][t];
}
function P(n, t) {
  return t in Zt.en ? a(n, t) : t.replaceAll("_", " ");
}
function w(n, t) {
  if (!t) return a(n, "missing");
  if (t.state === "unavailable") return a(n, "unavailable");
  if (t.state === "unknown" || t.state === "") return a(n, "unknown");
  if (n.formatEntityState) return n.formatEntityState(t);
  const e = t.attributes.unit_of_measurement;
  return `${P(n, t.state)}${e ? ` ${e}` : ""}`;
}
const jt = Dt`
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
`, Ee = Dt`
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
`, rt = [
  ["status_entity", "Installation status"],
  ["emergency_entity", "Emergency stop"],
  ["lock_entity", "Installation safety lock"],
  ["active_zone_entity", "Active zone / progress"],
  ["dose_entity", "Current dose"],
  ["pending_entity", "Open requests"],
  ["next_entity", "Next irrigation"],
  ["next_start_entity", "Expected start"],
  ["today_consumption_entity", "Today's consumption"],
  ["month_consumption_entity", "Monthly consumption"],
  ["runtime_today_entity", "Runtime today"],
  ["runtime_month_entity", "Runtime this month"],
  ["physical_meter_entity", "Corrected meter total"],
  ["model_quality_entity", "Model quality"],
  ["winter_entity", "Winter lock"],
  ["maintenance_entity", "Maintenance mode"],
  ["automation_release_entity", "Automatic release"],
  ["maintenance_due_entity", "Maintenance due"]
], ct = [
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
  ["calculation_entity", "Calculation"],
  ["water_today_entity", "Measured water today"],
  ["water_month_entity", "Measured water this month"],
  ["runtime_today_entity", "Runtime today"],
  ["runtime_month_entity", "Runtime this month"],
  ["next_irrigation_entity", "Next irrigation"]
], Nt = rt.map(([n]) => n), Tt = ct.map(([n]) => n), ze = {
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
}, Me = ["active", "pending", "next", "today", "month", "quality", "maintenance"], Ce = ["stop", "emergency", "suspend", "resume"], Oe = ["status", "today", "month", "next", "balance", "total", "recent", "quality", "calculation", "flow", "history"], qe = ["create", "start", "pause", "resume", "stop", "stop_skip", "suspend", "resume_auto", "archive", "restore"], j = class j extends E {
  setConfig(t) {
    this._config = { ...t };
  }
  updateValue(t, e) {
    const i = { ...this._config, [t]: e || void 0 };
    e || delete i[t], this._config = i, Se(this, i);
  }
  entitySelector(t, e, i) {
    const s = this.hass.language.toLowerCase().startsWith("de") ? ze[e] ?? e : e;
    return c`
      <label class="selector">
        <span>${s}${i ? " *" : ""}</span>
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
    return c`
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
    const e = gt(this._config, t);
    return c`
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
    const s = ke(this.hass, e);
    return c`
      <label class="selector">
        <span>${a(this.hass, e)}</span>
        <select
          data-testid="anchor-selector"
          .value=${String(this._config[t] ?? i ?? "")}
          @change=${(o) => this.updateValue(t, o.target.value)}
        >
          <option value="">${a(this.hass, "missing")}</option>
          ${s.map(
      (o) => c`<option value=${o.value}>${o.label}</option>`
    )}
        </select>
      </label>
    `;
  }
  choices(t, e) {
    const i = this._config[t] ?? e;
    return c`
      <div class="checks">
        ${e.map(
      (s) => c`
            <label class="check">
              <input
                type="checkbox"
                .checked=${i.includes(s)}
                @change=${(o) => {
        const r = o.target.checked;
        this.updateValue(
          t,
          r ? [...i, s] : i.filter((u) => u !== s)
        );
      }}
              />
              ${a(this.hass, s)}
            </label>
          `
    )}
      </div>
    `;
  }
};
j.styles = Ee, j.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 }
};
let Z = j;
class Ne extends Z {
  render() {
    if (!this.hass || !this._config) return l;
    const t = gt(this._config, Nt);
    return c`
      <div class="editor">
        <section>${this.configurationMode(Nt)}</section>
        ${t === "simple" ? c`<section>${this.anchorSelector("installation", "installation")}</section>` : c`
              <section>
                <h3>${a(this.hass, "required_entity")}</h3>
                ${this.entitySelector("status_entity", rt[0][1], !0)}
              </section>
              <section>
                <h3>${a(this.hass, "optional_entities")}</h3>
                ${rt.slice(1).map(([e, i]) => this.entitySelector(e, i, !1))}
              </section>
            `}
        <section>${this.displayMode()}</section>
        <section>
          <h3>${a(this.hass, "metrics")}</h3>
          ${this.choices("visible_metrics", Me)}
        </section>
        <section>
          <h3>${a(this.hass, "actions")}</h3>
          ${this.choices("visible_actions", Ce)}
        </section>
      </div>
    `;
  }
}
class Te extends Z {
  render() {
    if (!this.hass || !this._config) return l;
    const t = gt(this._config, Tt);
    return c`
      <div class="editor">
        <section>${this.configurationMode(Tt)}</section>
        ${t === "simple" ? c`<section>${this.anchorSelector("zone", "zone")}</section>` : c`
              <section>
                <h3>${a(this.hass, "required_entity")}</h3>
                ${this.entitySelector("zone_entity", ct[0][1], !0)}
              </section>
              <section>
                <h3>${a(this.hass, "optional_entities")}</h3>
                ${ct.slice(1).map(([e, i]) => this.entitySelector(e, i, !1))}
              </section>
            `}
        <section>${this.displayMode()}</section>
        <section>
          <h3>${a(this.hass, "metrics")}</h3>
          ${this.choices("visible_metrics", Oe)}
        </section>
        <section>
          <h3>${a(this.hass, "actions")}</h3>
          ${this.choices("visible_actions", qe)}
        </section>
      </div>
    `;
  }
}
const it = ["pending", "next", "today", "month", "meter"], Re = [], G = class G extends E {
  constructor() {
    super(...arguments), this._busy = !1, this._ordersOpen = !1, this._orders = [];
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
    return (this._config.visible_metrics ?? it).includes(t) ? c`<div class="metric"><span>${e}</span><strong>${w(this.hass, i)}</strong></div>` : l;
  }
  async call(t, e, i = {}) {
    if (e && !window.confirm(e)) return;
    const s = tt(this.hass, this._config), o = h(this.hass, s.status_entity), r = f(o, "config_entry_id");
    if (!r) {
      this._error = a(this.hass, "configuration_error");
      return;
    }
    this._busy = !0, this._error = void 0;
    try {
      await this.hass.callService(W, t, { config_entry_id: r, ...i });
    } catch (u) {
      this._error = `${a(this.hass, "action_failed")}: ${u instanceof Error ? u.message : String(u)}`;
    } finally {
      this._busy = !1;
    }
  }
  async openOrders() {
    const t = tt(this.hass, this._config), e = f(h(this.hass, t.status_entity), "config_entry_id");
    if (e) {
      this._ordersOpen = !0, this._busy = !0, this._error = void 0;
      try {
        const i = await this.hass.callService(
          W,
          "list_card_orders",
          { config_entry_id: e },
          void 0,
          !0
        );
        this._orders = i.orders ?? [];
      } catch (i) {
        this._error = `${a(this.hass, "action_failed")}: ${i instanceof Error ? i.message : String(i)}`;
      } finally {
        this._busy = !1;
      }
    }
  }
  target(t) {
    return `${String(t.target_value)} ${t.target_type === "volume" ? a(this.hass, "liters") : a(this.hass, "seconds")}`;
  }
  render() {
    if (!this.hass || !this._config) return l;
    const t = tt(this.hass, this._config);
    if (!t.status_entity || !h(this.hass, t.status_entity))
      return c`<ha-card><div class="card"><div class="warning"><ha-icon icon="mdi:water-alert"></ha-icon><span>${a(this.hass, "missing")}</span></div></div></ha-card>`;
    const e = h(this.hass, t.status_entity), i = h(this.hass, t.emergency_entity), s = h(this.hass, t.lock_entity), o = h(this.hass, t.winter_entity), r = h(this.hass, t.maintenance_entity), u = h(this.hass, t.automation_release_entity), d = h(this.hass, t.active_zone_entity), p = f(e, "config_entry_id"), y = Wt(d), _ = this._config.visible_actions ?? Re, v = e?.state ?? "unavailable", $ = i?.state === "on" || s?.state === "on", m = e?.attributes.volume_control_available === !0;
    return c`
      <ha-card>
        <div class="card ${this._config.display_mode === "compact" ? "compact" : ""}">
          <header>
            <div class="hero">
              <ha-icon .icon=${Ft(v)}></ha-icon>
              <div>
                <h2>${this._config.name ?? a(this.hass, "overview")}</h2>
                <strong>${F(e) ? P(this.hass, e.state) : w(this.hass, e)}</strong>
              </div>
            </div>
          </header>

          ${$ ? c`<div class="warning danger"><ha-icon icon="mdi:lock-alert-outline"></ha-icon><span>${i?.state === "on" ? a(this.hass, "emergency_stop") : a(this.hass, "safety_lock")}${f(s, "reason") ? `: ${f(s, "reason")}` : ""}</span></div>` : l}
          ${o?.state === "on" ? c`<div class="warning"><ha-icon icon="mdi:snowflake-alert"></ha-icon><span>${a(this.hass, "winter_lock")}</span></div>` : l}
          ${r?.state === "on" ? c`<div class="warning"><ha-icon icon="mdi:wrench-clock"></ha-icon><span>${a(this.hass, "maintenance_active")}</span></div>` : l}
          ${u?.state === "off" && f(u, "suspended_until") ? c`<div class="warning"><ha-icon icon="mdi:calendar-clock"></ha-icon><span>${a(this.hass, "automatic_suspended")}: ${f(u, "suspended_until")}</span></div>` : l}

          ${(this._config.visible_metrics ?? it).includes("active") && d ? c`
                <section>
                  <h3>${a(this.hass, "active_zone")}</h3>
                  <strong>${w(this.hass, d)}</strong>
                  ${t.dose_entity ? c`<div class="secondary">${a(this.hass, "dose")}: ${w(this.hass, h(this.hass, t.dose_entity))}</div>` : l}
                  ${y === void 0 ? l : c`<div class="secondary">${a(this.hass, "progress")}: ${Math.round(y)}%</div><progress max="100" .value=${y} aria-label=${a(this.hass, "progress")}></progress>`}
                </section>
              ` : l}

          <div class="metrics details">
            ${(this._config.visible_metrics ?? it).includes("pending") ? c`<button class="metric metric-button" data-testid="open-orders" ?disabled=${this._busy || !p} @click=${this.openOrders}><span>${a(this.hass, "pending")}</span><strong>${w(this.hass, h(this.hass, t.pending_entity))}</strong></button>` : l}
            ${this.metric("next", a(this.hass, "next_zone"), h(this.hass, t.next_entity))}
            ${this.metric("next", a(this.hass, "expected_start"), h(this.hass, t.next_start_entity))}
            ${this.metric("today", a(this.hass, m ? "water_today" : "runtime_today"), h(this.hass, m ? t.today_consumption_entity : t.runtime_today_entity))}
            ${this.metric("month", a(this.hass, m ? "water_month" : "runtime_month"), h(this.hass, m ? t.month_consumption_entity : t.runtime_month_entity))}
            ${this.metric("meter", a(this.hass, "corrected_meter"), h(this.hass, t.physical_meter_entity))}
            ${this.metric("quality", a(this.hass, "model_quality"), h(this.hass, t.model_quality_entity))}
            ${this.metric("maintenance", a(this.hass, "maintenance_due"), h(this.hass, t.maintenance_due_entity))}
          </div>

          ${this._error ? c`<div class="error" role="alert">${this._error}</div>` : l}
          <div class="actions">
            ${_.includes("stop") ? c`<button class="danger" ?disabled=${this._busy || !F(e) || !p} @click=${() => this.call("stop", a(this.hass, "confirm_stop"))}><ha-icon icon="mdi:stop-circle-outline"></ha-icon>${a(this.hass, "stop")}</button>` : l}
            <button class="danger emergency" data-testid="emergency-stop" ?disabled=${this._busy || !p} @click=${() => this.call("emergency_stop")}><ha-icon icon="mdi:alert-octagon-outline"></ha-icon>${a(this.hass, "emergency")}</button>
            ${_.includes("suspend") ? c`<button ?disabled=${this._busy || !p} @click=${() => this.call("suspend_automatic", a(this.hass, "confirm_suspend"), { until: new Date(Date.now() + 864e5).toISOString() })}><ha-icon icon="mdi:calendar-clock"></ha-icon>${a(this.hass, "suspend_24h")}</button>` : l}
            ${_.includes("resume") ? c`<button ?disabled=${this._busy || !p} @click=${() => this.call("resume_automatic", a(this.hass, "confirm_resume"))}><ha-icon icon="mdi:calendar-check"></ha-icon>${a(this.hass, "resume_automatic")}</button>` : l}
          </div>
          ${this._ordersOpen ? c`
            <dialog open aria-labelledby="orders-title">
              <div class="dialog-header"><h2 id="orders-title">${a(this.hass, "irrigation_orders")}</h2><button class="icon-button" aria-label=${a(this.hass, "close")} @click=${() => {
      this._ordersOpen = !1;
    }}>×</button></div>
              ${this._busy ? c`<p aria-live="polite">${a(this.hass, "loading")}</p>` : this._orders.length === 0 ? c`<p>${a(this.hass, "no_open_orders")}</p>` : c`
                <div class="table" role="table">
                  ${this._orders.map((b) => c`<div class="table-row" role="row"><strong>${String(b.zone)}</strong><span>${P(this.hass, String(b.source))}</span><span>${this.target(b)}</span><span>${String(b.expected_start)}</span><span>${P(this.hass, String(b.status))}</span></div>`)}
                </div>`}
            </dialog>` : l}
        </div>
      </ha-card>
    `;
  }
};
G.styles = jt, G.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 },
  _busy: { state: !0 },
  _error: { state: !0 },
  _ordersOpen: { state: !0 },
  _orders: { state: !0 }
};
let lt = G;
const Rt = ["status", "today", "month", "next"], Pe = [];
function st(n, t) {
  return t == null ? "–" : P(n, String(t));
}
const K = class K extends E {
  constructor() {
    super(...arguments), this._targetMode = "duration", this._targetValue = 600, this._hardLimit = 3600, this._busy = !1, this._manualOpen = !1, this._historyOpen = !1, this._conflictPolicy = "start_now", this._history = [], this._historyOffset = 0, this._historyTotal = 0, this._historySource = "", this._historyResult = "";
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
    return (this._config.visible_metrics ?? Rt).includes(t) ? c`<div class="metric"><span>${e}</span><strong>${w(this.hass, i)}</strong></div>` : l;
  }
  context() {
    const t = T(this.hass, this._config), e = h(this.hass, t.zone_entity), i = f(e, "config_entry_id"), s = f(e, "zone_subentry_id");
    return i && s ? { config_entry_id: i, zone_subentry_id: s } : void 0;
  }
  async perform(t, e, i) {
    if (!(i && !window.confirm(i))) {
      this._busy = !0, this._error = void 0;
      try {
        await this.hass.callService(W, t, e);
      } catch (s) {
        this._error = `${a(this.hass, "action_failed")}: ${s instanceof Error ? s.message : String(s)}`;
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
    const e = h(this.hass, T(this.hass, this._config).zone_entity), i = this._targetMode === "duration" ? C(e, "max_manual_duration_seconds") : C(e, "max_manual_volume_runtime_seconds"), s = this._targetMode === "duration" ? this._targetValue : this._hardLimit;
    if (i !== void 0 && s > i) {
      this._error = a(this.hass, "invalid_target");
      return;
    }
    const o = this._targetMode === "duration" ? { duration: this._targetValue } : { amount: this._targetValue, hard_time_limit: this._hardLimit }, r = e?.attributes.active_execution === !0;
    await this.perform("start_manual_from_card", {
      ...t,
      ...o,
      conflict_policy: r ? this._conflictPolicy : "start_now"
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
          W,
          "list_zone_history",
          i,
          void 0,
          !0
        );
        this._history = s.items ?? [], this._historyOffset = s.offset ?? t, this._historyTotal = s.total ?? 0;
      } catch (i) {
        this._error = `${a(this.hass, "action_failed")}: ${i instanceof Error ? i.message : String(i)}`;
      } finally {
        this._busy = !1;
      }
    }
  }
  historyTarget(t) {
    return `${String(t.target_value)} ${t.target_type === "volume" ? a(this.hass, "liters") : a(this.hass, "seconds")}`;
  }
  async requestAction(t) {
    const e = this.context(), i = h(this.hass, T(this.hass, this._config).request_entity), s = et(i, e?.zone_subentry_id);
    if (!e || !s?.requestId) {
      this._error = a(this.hass, "configuration_error");
      return;
    }
    await this.perform(t, {
      config_entry_id: e.config_entry_id,
      request_id: s.requestId
    });
  }
  async stop(t = !1) {
    const e = this.context(), i = h(this.hass, T(this.hass, this._config).request_entity), s = et(i, e?.zone_subentry_id);
    if (!e || !s) {
      this._error = a(this.hass, "configuration_error");
      return;
    }
    const o = s.executionId ? { execution_id: s.executionId } : { request_id: s.requestId };
    await this.perform(
      t ? "stop_and_skip" : "stop",
      { config_entry_id: e.config_entry_id, ...o },
      a(this.hass, t ? "confirm_stop_skip" : "confirm_stop")
    );
  }
  lockTimestamp(t) {
    const e = f(t, "occurred_at") ?? t.last_changed;
    if (!e) return;
    const i = new Date(e);
    return Number.isNaN(i.getTime()) ? e : new Intl.DateTimeFormat(this.hass.language, {
      dateStyle: "medium",
      timeStyle: "medium"
    }).format(i);
  }
  lockReason(t) {
    const e = f(t, "reason");
    if (!e) return;
    const i = [
      [" opened unexpectedly during startup", "unexpectedly_opened_during_startup"],
      [" opened unexpectedly", "unexpectedly_opened"],
      [" closed unexpectedly during irrigation", "unexpectedly_closed"]
    ];
    for (const [s, o] of i) {
      if (!e.endsWith(s)) continue;
      const r = e.slice(0, -s.length), u = h(this.hass, r)?.attributes.friendly_name;
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
    if (!this.hass || !this._config) return l;
    const t = T(this.hass, this._config);
    if (!t.zone_entity || !h(this.hass, t.zone_entity))
      return c`<ha-card><div class="card"><div class="warning"><ha-icon icon="mdi:water-alert"></ha-icon><span>${a(this.hass, "missing")}</span></div></div></ha-card>`;
    const e = h(this.hass, t.zone_entity), i = h(this.hass, t.automation_needed_entity), s = h(this.hass, t.safety_lock_entity), o = h(this.hass, t.installation_safety_lock_entity), r = s?.state === "on" ? s : o?.state === "on" ? o : void 0, u = h(this.hass, t.quality_entity), d = h(this.hass, t.status_entity), p = h(this.hass, t.automation_release_entity), y = h(this.hass, t.archived_entity), _ = h(this.hass, t.flow_deviation_entity), v = h(this.hass, t.active_zone_entity), $ = h(this.hass, t.request_entity), m = this.context(), b = et($, m?.zone_subentry_id), Y = Wt(v), yt = this._config.visible_metrics ?? Rt, x = this._config.visible_actions ?? Pe, Gt = this._config.name ?? e?.attributes.friendly_name ?? a(this.hass, "zone"), ft = u?.state ?? f(e, "measurement_quality"), vt = r && d ? { ...d, state: "safety_lock" } : d, Kt = r?.state === "on" || ["disabled", "installation_disabled", "safety_lock", "needs_reconfiguration"].includes(
      vt?.state ?? ""
    ), $t = r ? this.lockReason(r) : void 0, bt = r ? this.lockTimestamp(r) : void 0, Jt = C(e, "max_manual_duration_seconds") ?? 604800, Qt = C(e, "max_manual_volume_runtime_seconds") ?? 604800, Yt = s?.state === "on" ? "zone_safety_lock" : "installation_safety_lock";
    return c`
      <ha-card>
        <div class="card ${this._config.display_mode === "compact" ? "compact" : ""}">
          <header>
            <div class="hero">
              <ha-icon .icon=${Ft(r?.state === "on" ? "safety_lock" : i?.state ?? "unknown")}></ha-icon>
              <div>
                <h2>${Gt}</h2>
                <strong>${r?.state === "on" ? a(this.hass, "locked") : i?.state === "on" ? a(this.hass, "automation_needed") : i?.state === "off" ? a(this.hass, "automation_not_needed") : w(this.hass, i)}</strong>
              </div>
            </div>
          </header>

          ${r ? c`<div class="warning danger"><ha-icon icon="mdi:lock-alert-outline"></ha-icon><span><strong>${a(this.hass, Yt)}</strong>${$t ? c`<br />${a(this.hass, "lock_reason")}: ${$t}` : l}${bt ? c`<br />${a(this.hass, "lock_occurred_at")}: ${bt}` : l}</span></div>` : l}
          ${ft === "estimated" ? c`<div class="warning"><ha-icon icon="mdi:calculator-variant-outline"></ha-icon><span>${a(this.hass, "warning_estimated")}</span></div>` : ft === "unknown" ? c`<div class="warning"><ha-icon icon="mdi:help-circle-outline"></ha-icon><span>${a(this.hass, "warning_unknown")}</span></div>` : l}
          ${p?.state === "off" && f(p, "suspended_until") ? c`<div class="warning"><ha-icon icon="mdi:calendar-clock"></ha-icon><span>${a(this.hass, "automatic_suspended")}: ${f(p, "suspended_until")}</span></div>` : l}
          ${y?.state === "on" ? c`<div class="warning"><ha-icon icon="mdi:archive-outline"></ha-icon><span>${a(this.hass, "archived")}</span></div>` : l}
          ${_ && F(_) && Math.abs(Number(_.state)) >= 20 ? c`<div class="warning"><ha-icon icon="mdi:waves-arrow-up"></ha-icon><span>${a(this.hass, "flow_warning")}: ${w(this.hass, _)}</span></div>` : l}

          ${b && v && F(v) && Y !== void 0 ? c`<section><h3>${a(this.hass, "progress")}</h3><strong>${w(this.hass, v)} · ${Math.round(Y)}%</strong><progress max="100" .value=${Y} aria-label=${a(this.hass, "progress")}></progress></section>` : l}

          <div class="metrics">
            ${this.metric("status", a(this.hass, "status"), vt)}
            ${this.metric("today", a(this.hass, e?.attributes.volume_control_available === !0 ? "water_today" : "runtime_today"), h(this.hass, e?.attributes.volume_control_available === !0 ? t.water_today_entity : t.runtime_today_entity))}
            ${this.metric("month", a(this.hass, e?.attributes.volume_control_available === !0 ? "water_month" : "runtime_month"), h(this.hass, e?.attributes.volume_control_available === !0 ? t.water_month_entity : t.runtime_month_entity))}
            ${this.metric("next", a(this.hass, "next"), h(this.hass, t.next_irrigation_entity ?? t.next_window_entity))}
            ${this.metric("balance", a(this.hass, "water_balance"), h(this.hass, t.deficit_entity))}
            ${this.metric("balance", a(this.hass, "target"), h(this.hass, t.target_entity))}
            ${yt.includes("balance") ? this.metric("balance", a(this.hass, "explanation"), h(this.hass, t.planning_reason_entity)) : l}
            ${this.metric("total", a(this.hass, "total"), e)}
            ${this.metric("recent", a(this.hass, "last_delivered"), h(this.hass, t.last_delivered_entity))}
            ${this.metric("recent", a(this.hass, "last_duration"), h(this.hass, t.last_duration_entity))}
            ${this.metric("quality", a(this.hass, "quality"), u)}
            ${this.metric("calculation", a(this.hass, "coverage"), h(this.hass, t.coverage_entity))}
            ${t.calculation_entity ? this.metric("calculation", a(this.hass, "explanation"), h(this.hass, t.calculation_entity)) : l}
            ${this.metric("flow", a(this.hass, "expected_flow"), h(this.hass, t.expected_flow_entity))}
            ${this.metric("flow", a(this.hass, "actual_flow"), h(this.hass, t.actual_flow_entity))}
            ${this.metric("flow", a(this.hass, "flow_deviation"), _)}
          </div>
          ${yt.includes("history") && Array.isArray(e?.attributes.recent_history) ? c`<section class="details"><h3>${a(this.hass, "history")}</h3>${e.attributes.recent_history.slice(-3).reverse().map((g) => c`<div class="secondary">${String(g.ended_at ?? g.created_at ?? "")} · ${String(g.result ?? g.status ?? "")}</div>`)}</section>` : l}

          ${this._error ? c`<div class="error" role="alert">${this._error}</div>` : l}
          <div class="actions">
            <button class="primary" data-testid="manual-irrigation" ?disabled=${this._busy || Kt || !m} @click=${() => this.openManual(e)}><ha-icon icon="mdi:sprinkler-variant"></ha-icon>${a(this.hass, "manual_water")}</button>
            <button data-testid="show-history" ?disabled=${this._busy || !m} @click=${() => this.loadHistory(0)}><ha-icon icon="mdi:history"></ha-icon>${a(this.hass, "show_history")}</button>
            ${x.includes("pause") ? c`<button ?disabled=${this._busy || !b?.requestId} @click=${() => this.requestAction("pause_request")}><ha-icon icon="mdi:pause"></ha-icon>${a(this.hass, "pause")}</button>` : l}
            ${x.includes("resume") ? c`<button ?disabled=${this._busy || !b?.requestId} @click=${() => this.requestAction("resume_request")}><ha-icon icon="mdi:play-pause"></ha-icon>${a(this.hass, "resume")}</button>` : l}
            ${x.includes("stop") ? c`<button class="danger" ?disabled=${this._busy || !b} @click=${() => this.stop()}><ha-icon icon="mdi:stop-circle-outline"></ha-icon>${a(this.hass, "stop")}</button>` : l}
            ${x.includes("stop_skip") ? c`<button class="danger" ?disabled=${this._busy || !b} @click=${() => this.stop(!0)}><ha-icon icon="mdi:skip-next-circle-outline"></ha-icon>${a(this.hass, "stop_skip")}</button>` : l}
            ${x.includes("suspend") ? c`<button ?disabled=${this._busy || !m || y?.state === "on"} @click=${() => m && this.perform("suspend_automatic", { ...m, until: new Date(Date.now() + 864e5).toISOString() })}><ha-icon icon="mdi:calendar-clock"></ha-icon>${a(this.hass, "suspend_24h")}</button>` : l}
            ${x.includes("resume_auto") ? c`<button ?disabled=${this._busy || !m} @click=${() => m && this.perform("resume_automatic", m)}><ha-icon icon="mdi:calendar-check"></ha-icon>${a(this.hass, "resume_automatic")}</button>` : l}
            ${r ? c`<button data-testid="reset-safety" class="danger" ?disabled=${this._busy || !m} @click=${() => m && this.resetSafety(m, s)}><ha-icon icon="mdi:lock-open-alert-outline"></ha-icon>${a(this.hass, "reset_safety")}</button>` : l}
            ${x.includes("archive") ? c`<button ?disabled=${this._busy || !m || y?.state === "on"} @click=${() => m && this.perform("archive_zone", m, a(this.hass, "confirm_archive"))}><ha-icon icon="mdi:archive-arrow-down-outline"></ha-icon>${a(this.hass, "archive")}</button>` : l}
            ${x.includes("restore") ? c`<button ?disabled=${this._busy || !m || y?.state !== "on"} @click=${() => m && this.perform("restore_zone", m)}><ha-icon icon="mdi:archive-arrow-up-outline"></ha-icon>${a(this.hass, "restore")}</button>` : l}
          </div>
          ${this._manualOpen ? c`
            <dialog open aria-labelledby="manual-title">
              <div class="dialog-header"><h2 id="manual-title">${a(this.hass, "manual_water")}</h2><button class="icon-button" aria-label=${a(this.hass, "close")} @click=${() => {
      this._manualOpen = !1;
    }}>×</button></div>
              <div class="form-grid">
                <label class="field"><span>${a(this.hass, "target")}</span><select data-testid="target-mode" .value=${this._targetMode} @change=${(g) => {
      this._targetMode = g.target.value;
    }}><option value="duration">${a(this.hass, "duration_mode")}</option>${e?.attributes.volume_control_available === !0 ? c`<option value="amount">${a(this.hass, "amount_mode")}</option>` : l}</select></label>
                <label class="field"><span>${this._targetMode === "duration" ? a(this.hass, "duration") : a(this.hass, "amount")}</span><input data-testid="manual-target" type="number" min="0.001" max=${this._targetMode === "duration" ? String(Jt) : "1000000"} step=${this._targetMode === "duration" ? "1" : "0.1"} .value=${String(this._targetValue)} @input=${(g) => {
      this._targetValue = Number(g.target.value);
    }} /><span>${this._targetMode === "duration" ? a(this.hass, "seconds") : a(this.hass, "liters")}</span></label>
                ${this._targetMode === "amount" ? c`<label class="field"><span>${a(this.hass, "hard_limit")}</span><input data-testid="hard-limit" type="number" min="0.001" max=${String(Qt)} step="1" .value=${String(this._hardLimit)} @input=${(g) => {
      this._hardLimit = Number(g.target.value);
    }} /><span>${a(this.hass, "seconds")}</span></label>` : l}
                ${e?.attributes.active_execution === !0 ? c`<label class="field"><span>${a(this.hass, "active_execution_choice")}</span><select data-testid="conflict-policy" .value=${this._conflictPolicy} @change=${(g) => {
      this._conflictPolicy = g.target.value;
    }}><option value="stop_active">${a(this.hass, "stop_active_start_now")}</option><option value="priority_next">${a(this.hass, "finish_then_priority")}</option></select></label>` : l}
              </div>
              ${this._error ? c`<div class="error" role="alert">${this._error}</div>` : l}
              <div class="actions dialog-actions"><button data-testid="submit-manual" class="primary" ?disabled=${this._busy} @click=${this.request}>${a(this.hass, "start")}</button></div>
            </dialog>` : l}
          ${this._historyOpen ? c`
            <dialog open aria-labelledby="history-title">
              <div class="dialog-header"><h2 id="history-title">${a(this.hass, "irrigation_history")}</h2><button class="icon-button" aria-label=${a(this.hass, "close")} @click=${() => {
      this._historyOpen = !1;
    }}>×</button></div>
              <div class="filters"><label class="field"><span>${a(this.hass, "source")}</span><select .value=${this._historySource} @change=${(g) => {
      this._historySource = g.target.value, this.loadHistory(0);
    }}><option value="">${a(this.hass, "all")}</option><option value="manual">${a(this.hass, "manual")}</option><option value="automatic">${a(this.hass, "automatic")}</option></select></label><label class="field"><span>${a(this.hass, "result")}</span><select .value=${this._historyResult} @change=${(g) => {
      this._historyResult = g.target.value, this.loadHistory(0);
    }}><option value="">${a(this.hass, "all")}</option><option value="completed">${a(this.hass, "completed")}</option><option value="failed">${a(this.hass, "failed")}</option><option value="cancelled">${a(this.hass, "cancelled")}</option></select></label></div>
              ${this._busy ? c`<p aria-live="polite">${a(this.hass, "loading")}</p>` : c`<div class="history-list">${this._history.map((g) => c`<article><strong>${this.historyTarget(g)}</strong><span>${String(g.started_at)} – ${String(g.ended_at ?? "")}</span><span>${st(this.hass, g.source)} · ${st(this.hass, g.result)} · ${String(g.actual_duration)} s${g.actual_water == null ? "" : ` · ${String(g.actual_water)} L`} · ${st(this.hass, g.completion_reason)}</span></article>`)}</div>`}
              <div class="actions"><button ?disabled=${this._busy || this._historyOffset === 0} @click=${() => this.loadHistory(Math.max(0, this._historyOffset - 20))}>${a(this.hass, "previous")}</button><span>${this._historyTotal === 0 ? 0 : this._historyOffset + 1}–${Math.min(this._historyOffset + this._history.length, this._historyTotal)} / ${this._historyTotal}</span><button ?disabled=${this._busy || this._historyOffset + this._history.length >= this._historyTotal} @click=${() => this.loadHistory(this._historyOffset + 20)}>${a(this.hass, "next_page")}</button></div>
            </dialog>` : l}
        </div>
      </ha-card>
    `;
  }
};
K.styles = jt, K.properties = {
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
let ht = K;
const De = [
  ["irrigation-manager-overview-card", lt],
  ["irrigation-manager-zone-card", ht],
  ["irrigation-manager-overview-card-editor", Ne],
  ["irrigation-manager-zone-card-editor", Te]
];
for (const [n, t] of De)
  customElements.get(n) || customElements.define(n, t);
window.customCards = window.customCards ?? [];
for (const n of [
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
  window.customCards.some((t) => t.type === n.type) || window.customCards.push(n);
