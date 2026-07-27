const R = globalThis, it = R.ShadowRoot && (R.ShadyCSS === void 0 || R.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype, st = /* @__PURE__ */ Symbol(), ot = /* @__PURE__ */ new WeakMap();
let $t = class {
  constructor(t, e, i) {
    if (this._$cssResult$ = !0, i !== st) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
    this.cssText = t, this.t = e;
  }
  get styleSheet() {
    let t = this.o;
    const e = this.t;
    if (it && t === void 0) {
      const i = e !== void 0 && e.length === 1;
      i && (t = ot.get(e)), t === void 0 && ((this.o = t = new CSSStyleSheet()).replaceSync(this.cssText), i && ot.set(e, t));
    }
    return t;
  }
  toString() {
    return this.cssText;
  }
};
const Dt = (s) => new $t(typeof s == "string" ? s : s + "", void 0, st), bt = (s, ...t) => {
  const e = s.length === 1 ? s[0] : t.reduce((i, r, n) => i + ((o) => {
    if (o._$cssResult$ === !0) return o.cssText;
    if (typeof o == "number") return o;
    throw Error("Value passed to 'css' function must be a 'css' function result: " + o + ". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.");
  })(r) + s[n + 1], s[0]);
  return new $t(e, s, st);
}, Tt = (s, t) => {
  if (it) s.adoptedStyleSheets = t.map((e) => e instanceof CSSStyleSheet ? e : e.styleSheet);
  else for (const e of t) {
    const i = document.createElement("style"), r = R.litNonce;
    r !== void 0 && i.setAttribute("nonce", r), i.textContent = e.cssText, s.appendChild(i);
  }
}, lt = it ? (s) => s : (s) => s instanceof CSSStyleSheet ? ((t) => {
  let e = "";
  for (const i of t.cssRules) e += i.cssText;
  return Dt(e);
})(s) : s;
const { is: Pt, defineProperty: Ht, getOwnPropertyDescriptor: Nt, getOwnPropertyNames: Ut, getOwnPropertySymbols: Rt, getPrototypeOf: It } = Object, q = globalThis, ht = q.trustedTypes, Bt = ht ? ht.emptyScript : "", Lt = q.reactiveElementPolyfillSupport, M = (s, t) => s, Y = { toAttribute(s, t) {
  switch (t) {
    case Boolean:
      s = s ? Bt : null;
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
} }, xt = (s, t) => !Pt(s, t), ct = { attribute: !0, type: String, converter: Y, reflect: !1, useDefault: !1, hasChanged: xt };
Symbol.metadata ??= /* @__PURE__ */ Symbol("metadata"), q.litPropertyMetadata ??= /* @__PURE__ */ new WeakMap();
let w = class extends HTMLElement {
  static addInitializer(t) {
    this._$Ei(), (this.l ??= []).push(t);
  }
  static get observedAttributes() {
    return this.finalize(), this._$Eh && [...this._$Eh.keys()];
  }
  static createProperty(t, e = ct) {
    if (e.state && (e.attribute = !1), this._$Ei(), this.prototype.hasOwnProperty(t) && ((e = Object.create(e)).wrapped = !0), this.elementProperties.set(t, e), !e.noAccessor) {
      const i = /* @__PURE__ */ Symbol(), r = this.getPropertyDescriptor(t, i, e);
      r !== void 0 && Ht(this.prototype, t, r);
    }
  }
  static getPropertyDescriptor(t, e, i) {
    const { get: r, set: n } = Nt(this.prototype, t) ?? { get() {
      return this[e];
    }, set(o) {
      this[e] = o;
    } };
    return { get: r, set(o) {
      const u = r?.call(this);
      n?.call(this, o), this.requestUpdate(t, u, i);
    }, configurable: !0, enumerable: !0 };
  }
  static getPropertyOptions(t) {
    return this.elementProperties.get(t) ?? ct;
  }
  static _$Ei() {
    if (this.hasOwnProperty(M("elementProperties"))) return;
    const t = It(this);
    t.finalize(), t.l !== void 0 && (this.l = [...t.l]), this.elementProperties = new Map(t.elementProperties);
  }
  static finalize() {
    if (this.hasOwnProperty(M("finalized"))) return;
    if (this.finalized = !0, this._$Ei(), this.hasOwnProperty(M("properties"))) {
      const e = this.properties, i = [...Ut(e), ...Rt(e)];
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
      for (const r of i) e.unshift(lt(r));
    } else t !== void 0 && e.push(lt(t));
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
    const i = this.constructor.elementProperties.get(t), r = this.constructor._$Eu(t, i);
    if (r !== void 0 && i.reflect === !0) {
      const n = (i.converter?.toAttribute !== void 0 ? i.converter : Y).toAttribute(e, i.type);
      this._$Em = t, n == null ? this.removeAttribute(r) : this.setAttribute(r, n), this._$Em = null;
    }
  }
  _$AK(t, e) {
    const i = this.constructor, r = i._$Eh.get(t);
    if (r !== void 0 && this._$Em !== r) {
      const n = i.getPropertyOptions(r), o = typeof n.converter == "function" ? { fromAttribute: n.converter } : n.converter?.fromAttribute !== void 0 ? n.converter : Y;
      this._$Em = r;
      const u = o.fromAttribute(e, n.type);
      this[r] = u ?? this._$Ej?.get(r) ?? u, this._$Em = null;
    }
  }
  requestUpdate(t, e, i, r = !1, n) {
    if (t !== void 0) {
      const o = this.constructor;
      if (r === !1 && (n = this[t]), i ??= o.getPropertyOptions(t), !((i.hasChanged ?? xt)(n, e) || i.useDefault && i.reflect && n === this._$Ej?.get(t) && !this.hasAttribute(o._$Eu(t, i)))) return;
      this.C(t, e, i);
    }
    this.isUpdatePending === !1 && (this._$ES = this._$EP());
  }
  C(t, e, { useDefault: i, reflect: r, wrapped: n }, o) {
    i && !(this._$Ej ??= /* @__PURE__ */ new Map()).has(t) && (this._$Ej.set(t, o ?? e ?? this[t]), n !== !0 || o !== void 0) || (this._$AL.has(t) || (this.hasUpdated || i || (e = void 0), this._$AL.set(t, e)), r === !0 && this._$Em !== t && (this._$Eq ??= /* @__PURE__ */ new Set()).add(t));
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
        for (const [r, n] of this._$Ep) this[r] = n;
        this._$Ep = void 0;
      }
      const i = this.constructor.elementProperties;
      if (i.size > 0) for (const [r, n] of i) {
        const { wrapped: o } = n, u = this[r];
        o !== !0 || this._$AL.has(r) || u === void 0 || this.C(r, void 0, n, u);
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
w.elementStyles = [], w.shadowRootOptions = { mode: "open" }, w[M("elementProperties")] = /* @__PURE__ */ new Map(), w[M("finalized")] = /* @__PURE__ */ new Map(), Lt?.({ ReactiveElement: w }), (q.reactiveElementVersions ??= []).push("2.1.2");
const rt = globalThis, dt = (s) => s, I = rt.trustedTypes, ut = I ? I.createPolicy("lit-html", { createHTML: (s) => s }) : void 0, wt = "$lit$", y = `lit$${Math.random().toFixed(9).slice(2)}$`, St = "?" + y, Vt = `<${St}>`, x = document, D = () => x.createComment(""), T = (s) => s === null || typeof s != "object" && typeof s != "function", nt = Array.isArray, jt = (s) => nt(s) || typeof s?.[Symbol.iterator] == "function", G = `[\x20\t\n\f\r]`, k = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g, pt = /-->/g, _t = />/g, v = RegExp(`>|${G}(?:([^\\s"'>=/]+)(${G}*=${G}*(?:[^\x20\t\n\f\r"'\`<>=]|("|')|))|$)`, "g"), gt = /'/g, mt = /"/g, At = /^(?:script|style|textarea|title)$/i, Wt = (s) => (t, ...e) => ({ _$litType$: s, strings: t, values: e }), c = Wt(1), E = /* @__PURE__ */ Symbol.for("lit-noChange"), d = /* @__PURE__ */ Symbol.for("lit-nothing"), ft = /* @__PURE__ */ new WeakMap(), $ = x.createTreeWalker(x, 129);
function Et(s, t) {
  if (!nt(s) || !s.hasOwnProperty("raw")) throw Error("invalid template strings array");
  return ut !== void 0 ? ut.createHTML(t) : t;
}
const Ft = (s, t) => {
  const e = s.length - 1, i = [];
  let r, n = t === 2 ? "<svg>" : t === 3 ? "<math>" : "", o = k;
  for (let u = 0; u < e; u++) {
    const h = s[u];
    let p, l, _ = -1, m = 0;
    for (; m < h.length && (o.lastIndex = m, l = o.exec(h), l !== null); ) m = o.lastIndex, o === k ? l[1] === "!--" ? o = pt : l[1] !== void 0 ? o = _t : l[2] !== void 0 ? (At.test(l[2]) && (r = RegExp("</" + l[2], "g")), o = v) : l[3] !== void 0 && (o = v) : o === v ? l[0] === ">" ? (o = r ?? k, _ = -1) : l[1] === void 0 ? _ = -2 : (_ = o.lastIndex - l[2].length, p = l[1], o = l[3] === void 0 ? v : l[3] === '"' ? mt : gt) : o === mt || o === gt ? o = v : o === pt || o === _t ? o = k : (o = v, r = void 0);
    const f = o === v && s[u + 1].startsWith("/>") ? " " : "";
    n += o === k ? h + Vt : _ >= 0 ? (i.push(p), h.slice(0, _) + wt + h.slice(_) + y + f) : h + y + (_ === -2 ? u : f);
  }
  return [Et(s, n + (s[e] || "<?>") + (t === 2 ? "</svg>" : t === 3 ? "</math>" : "")), i];
};
class P {
  constructor({ strings: t, _$litType$: e }, i) {
    let r;
    this.parts = [];
    let n = 0, o = 0;
    const u = t.length - 1, h = this.parts, [p, l] = Ft(t, e);
    if (this.el = P.createElement(p, i), $.currentNode = this.el.content, e === 2 || e === 3) {
      const _ = this.el.content.firstChild;
      _.replaceWith(..._.childNodes);
    }
    for (; (r = $.nextNode()) !== null && h.length < u; ) {
      if (r.nodeType === 1) {
        if (r.hasAttributes()) for (const _ of r.getAttributeNames()) if (_.endsWith(wt)) {
          const m = l[o++], f = r.getAttribute(_).split(y), N = /([.?@])?(.*)/.exec(m);
          h.push({ type: 1, index: n, name: N[2], strings: f, ctor: N[1] === "." ? Zt : N[1] === "?" ? Kt : N[1] === "@" ? Gt : Z }), r.removeAttribute(_);
        } else _.startsWith(y) && (h.push({ type: 6, index: n }), r.removeAttribute(_));
        if (At.test(r.tagName)) {
          const _ = r.textContent.split(y), m = _.length - 1;
          if (m > 0) {
            r.textContent = I ? I.emptyScript : "";
            for (let f = 0; f < m; f++) r.append(_[f], D()), $.nextNode(), h.push({ type: 2, index: ++n });
            r.append(_[m], D());
          }
        }
      } else if (r.nodeType === 8) if (r.data === St) h.push({ type: 2, index: n });
      else {
        let _ = -1;
        for (; (_ = r.data.indexOf(y, _ + 1)) !== -1; ) h.push({ type: 7, index: n }), _ += y.length - 1;
      }
      n++;
    }
  }
  static createElement(t, e) {
    const i = x.createElement("template");
    return i.innerHTML = t, i;
  }
}
function z(s, t, e = s, i) {
  if (t === E) return t;
  let r = i !== void 0 ? e._$Co?.[i] : e._$Cl;
  const n = T(t) ? void 0 : t._$litDirective$;
  return r?.constructor !== n && (r?._$AO?.(!1), n === void 0 ? r = void 0 : (r = new n(s), r._$AT(s, e, i)), i !== void 0 ? (e._$Co ??= [])[i] = r : e._$Cl = r), r !== void 0 && (t = z(s, r._$AS(s, t.values), r, i)), t;
}
class qt {
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
    const { el: { content: e }, parts: i } = this._$AD, r = (t?.creationScope ?? x).importNode(e, !0);
    $.currentNode = r;
    let n = $.nextNode(), o = 0, u = 0, h = i[0];
    for (; h !== void 0; ) {
      if (o === h.index) {
        let p;
        h.type === 2 ? p = new H(n, n.nextSibling, this, t) : h.type === 1 ? p = new h.ctor(n, h.name, h.strings, this, t) : h.type === 6 && (p = new Jt(n, this, t)), this._$AV.push(p), h = i[++u];
      }
      o !== h?.index && (n = $.nextNode(), o++);
    }
    return $.currentNode = x, r;
  }
  p(t) {
    let e = 0;
    for (const i of this._$AV) i !== void 0 && (i.strings !== void 0 ? (i._$AI(t, i, e), e += i.strings.length - 2) : i._$AI(t[e])), e++;
  }
}
class H {
  get _$AU() {
    return this._$AM?._$AU ?? this._$Cv;
  }
  constructor(t, e, i, r) {
    this.type = 2, this._$AH = d, this._$AN = void 0, this._$AA = t, this._$AB = e, this._$AM = i, this.options = r, this._$Cv = r?.isConnected ?? !0;
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
    t = z(this, t, e), T(t) ? t === d || t == null || t === "" ? (this._$AH !== d && this._$AR(), this._$AH = d) : t !== this._$AH && t !== E && this._(t) : t._$litType$ !== void 0 ? this.$(t) : t.nodeType !== void 0 ? this.T(t) : jt(t) ? this.k(t) : this._(t);
  }
  O(t) {
    return this._$AA.parentNode.insertBefore(t, this._$AB);
  }
  T(t) {
    this._$AH !== t && (this._$AR(), this._$AH = this.O(t));
  }
  _(t) {
    this._$AH !== d && T(this._$AH) ? this._$AA.nextSibling.data = t : this.T(x.createTextNode(t)), this._$AH = t;
  }
  $(t) {
    const { values: e, _$litType$: i } = t, r = typeof i == "number" ? this._$AC(t) : (i.el === void 0 && (i.el = P.createElement(Et(i.h, i.h[0]), this.options)), i);
    if (this._$AH?._$AD === r) this._$AH.p(e);
    else {
      const n = new qt(r, this), o = n.u(this.options);
      n.p(e), this.T(o), this._$AH = n;
    }
  }
  _$AC(t) {
    let e = ft.get(t.strings);
    return e === void 0 && ft.set(t.strings, e = new P(t)), e;
  }
  k(t) {
    nt(this._$AH) || (this._$AH = [], this._$AR());
    const e = this._$AH;
    let i, r = 0;
    for (const n of t) r === e.length ? e.push(i = new H(this.O(D()), this.O(D()), this, this.options)) : i = e[r], i._$AI(n), r++;
    r < e.length && (this._$AR(i && i._$AB.nextSibling, r), e.length = r);
  }
  _$AR(t = this._$AA.nextSibling, e) {
    for (this._$AP?.(!1, !0, e); t !== this._$AB; ) {
      const i = dt(t).nextSibling;
      dt(t).remove(), t = i;
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
  constructor(t, e, i, r, n) {
    this.type = 1, this._$AH = d, this._$AN = void 0, this.element = t, this.name = e, this._$AM = r, this.options = n, i.length > 2 || i[0] !== "" || i[1] !== "" ? (this._$AH = Array(i.length - 1).fill(new String()), this.strings = i) : this._$AH = d;
  }
  _$AI(t, e = this, i, r) {
    const n = this.strings;
    let o = !1;
    if (n === void 0) t = z(this, t, e, 0), o = !T(t) || t !== this._$AH && t !== E, o && (this._$AH = t);
    else {
      const u = t;
      let h, p;
      for (t = n[0], h = 0; h < n.length - 1; h++) p = z(this, u[i + h], e, h), p === E && (p = this._$AH[h]), o ||= !T(p) || p !== this._$AH[h], p === d ? t = d : t !== d && (t += (p ?? "") + n[h + 1]), this._$AH[h] = p;
    }
    o && !r && this.j(t);
  }
  j(t) {
    t === d ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, t ?? "");
  }
}
class Zt extends Z {
  constructor() {
    super(...arguments), this.type = 3;
  }
  j(t) {
    this.element[this.name] = t === d ? void 0 : t;
  }
}
class Kt extends Z {
  constructor() {
    super(...arguments), this.type = 4;
  }
  j(t) {
    this.element.toggleAttribute(this.name, !!t && t !== d);
  }
}
class Gt extends Z {
  constructor(t, e, i, r, n) {
    super(t, e, i, r, n), this.type = 5;
  }
  _$AI(t, e = this) {
    if ((t = z(this, t, e, 0) ?? d) === E) return;
    const i = this._$AH, r = t === d && i !== d || t.capture !== i.capture || t.once !== i.once || t.passive !== i.passive, n = t !== d && (i === d || r);
    r && this.element.removeEventListener(this.name, this, i), n && this.element.addEventListener(this.name, this, t), this._$AH = t;
  }
  handleEvent(t) {
    typeof this._$AH == "function" ? this._$AH.call(this.options?.host ?? this.element, t) : this._$AH.handleEvent(t);
  }
}
class Jt {
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
const Qt = rt.litHtmlPolyfillSupport;
Qt?.(P, H), (rt.litHtmlVersions ??= []).push("3.3.3");
const Xt = (s, t, e) => {
  const i = e?.renderBefore ?? t;
  let r = i._$litPart$;
  if (r === void 0) {
    const n = e?.renderBefore ?? null;
    i._$litPart$ = r = new H(t.insertBefore(D(), n), n, void 0, e ?? {});
  }
  return r._$AI(s), r;
};
const at = globalThis;
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
    this.hasUpdated || (this.renderOptions.isConnected = this.isConnected), super.update(t), this._$Do = Xt(e, this.renderRoot, this.renderOptions);
  }
  connectedCallback() {
    super.connectedCallback(), this._$Do?.setConnected(!0);
  }
  disconnectedCallback() {
    super.disconnectedCallback(), this._$Do?.setConnected(!1);
  }
  render() {
    return E;
  }
}
b._$litElement$ = !0, b.finalized = !0, at.litElementHydrateSupport?.({ LitElement: b });
const Yt = at.litElementPolyfillSupport;
Yt?.({ LitElement: b });
(at.litElementVersions ??= []).push("4.2.2");
const S = "irrigation_manager", te = /* @__PURE__ */ new Set(["unknown", "unavailable"]);
function yt(s) {
  const t = /^(\d+):([0-5]\d):([0-5]\d(?:\.\d+)?)$/.exec(s.trim());
  if (!t) return;
  const e = Number(t[1]) * 3600 + Number(t[2]) * 60 + Number(t[3]);
  return Number.isFinite(e) && e > 0 ? e : void 0;
}
function vt(s) {
  const t = Math.floor(s / 3600), e = Math.floor(s % 3600 / 60), i = s - t * 3600 - e * 60, r = i.toFixed(6).replace(/0+$/, "").replace(/\.$/, ""), n = Number.isInteger(i) ? String(i).padStart(2, "0") : `${i < 10 ? "0" : ""}${r}`;
  return `${String(t).padStart(2, "0")}:${String(e).padStart(2, "0")}:${n}`;
}
function zt(s) {
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
const ee = {
  status: "status_entity",
  pending: "pending_entity",
  next: "next_entity",
  next_start: "next_start_entity",
  today_consumption: "today_consumption_entity",
  month_consumption: "month_consumption_entity",
  runtime_today: "runtime_today_entity",
  runtime_month: "runtime_month_entity",
  physical_meter: "physical_meter_entity"
}, ie = {
  anchor: "zone_entity",
  zone: "zone_entity",
  status: "status_entity",
  water_today: "water_today_entity",
  water_month: "water_month_entity",
  runtime_today: "runtime_today_entity",
  runtime_month: "runtime_month_entity",
  next_irrigation: "next_irrigation_entity"
};
function L(s, t) {
  const e = s?.attributes[t];
  return !e || typeof e != "object" || Array.isArray(e) ? {} : Object.fromEntries(
    Object.entries(e).filter(
      (i) => typeof i[1] == "string" && i[1].includes(".")
    )
  );
}
function kt(s, t, e) {
  const i = { ...s };
  for (const [r, n] of Object.entries(e)) {
    const u = s[n] || t[r];
    u && Object.assign(i, { [n]: u });
  }
  return i;
}
function J(s, t) {
  const e = t.entity ? s.states[t.entity] : void 0, i = { ...t };
  return kt(i, L(e, "card_entities"), ee);
}
function Q(s, t) {
  const e = t.entity ? s.states[t.entity] : void 0, i = { ...t }, r = kt(i, L(e, "card_entities"), ie);
  return !r.zone_entity && e && (r.zone_entity = e.entity_id), !r.status_entity && e && (r.status_entity = e.entity_id), r;
}
function K(s, t) {
  if (!s || !s.entity_id.startsWith("sensor.")) return !1;
  const e = s.attributes.config_entry_id;
  if (typeof e != "string" || !e) return !1;
  if (t === "installation")
    return typeof s.attributes.zone_subentry_id == "string" ? !1 : L(s, "card_entities").status === s.entity_id;
  const i = s.attributes.zone_subentry_id;
  if (typeof i != "string" || !i) return !1;
  const r = L(s, "card_entities");
  return r.anchor ? r.anchor === s.entity_id : r.zone === s.entity_id;
}
function se(s, t) {
  return Object.values(s.states).filter((e) => K(e, t)).map((e) => e.entity_id);
}
function g(s, t) {
  return t ? s.states[t] : void 0;
}
function re(s) {
  return !!(s && !te.has(s.state));
}
function A(s, t) {
  const e = s?.attributes[t];
  return typeof e == "string" && e ? e : void 0;
}
function U(s, t) {
  const e = s?.attributes[t];
  return typeof e == "number" && Number.isFinite(e) ? e : void 0;
}
function Mt(s) {
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
function ne(s, t) {
  s.dispatchEvent(
    new CustomEvent("config-changed", {
      detail: { config: t },
      bubbles: !0,
      composed: !0
    })
  );
}
const Ot = {
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
    invalid_duration: "Enter the duration as HH:MM:SS.",
    hard_limit_required: "Enter the maximum duration as HH:MM:SS.",
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
    invalid_duration: "Die Dauer als HH:MM:SS eingeben.",
    hard_limit_required: "Die maximale Dauer als HH:MM:SS eingeben.",
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
function a(s, t) {
  const e = s.language?.toLowerCase().startsWith("de") ? "de" : "en";
  return Ot[e][t];
}
function O(s, t) {
  return t in Ot.en ? a(s, t) : t.replaceAll("_", " ");
}
function C(s, t) {
  if (!t) return a(s, "missing");
  if (t.state === "unavailable") return a(s, "unavailable");
  if (t.state === "unknown" || t.state === "") return a(s, "unknown");
  if (s.formatEntityState) return s.formatEntityState(t);
  const e = t.attributes.unit_of_measurement;
  return `${O(s, t.state)}${e ? ` ${e}` : ""}`;
}
const Ct = bt`
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
  }
`, ae = bt`
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
`, j = class j extends b {
  setConfig(t) {
    this._config = { ...t };
  }
  updateValue(t, e) {
    const i = { ...this._config, [t]: e };
    (e === void 0 || e === "") && delete i[t], this._config = i, ne(this, i);
  }
  valueChanged(t) {
    const e = t.detail?.value;
    this.updateValue("entity", typeof e == "string" ? e : void 0);
  }
  anchorSelector(t) {
    const e = this._config.entity ? this.hass.states[this._config.entity] : void 0, i = !!(this._config.entity && !K(e, t));
    return c`
      <label class="selector">
        <span>${a(this.hass, t)}</span>
        <ha-selector
          data-testid="anchor-selector"
          .hass=${this.hass}
          .value=${this._config.entity ?? ""}
          .selector=${{
      entity: {
        include_entities: se(this.hass, t),
        filter: {
          integration: S,
          domain: "sensor",
          device_class: "enum"
        }
      }
    }}
          @value-changed=${this.valueChanged}
        ></ha-selector>
        ${i ? c`<span class="error" role="alert">${a(
      this.hass,
      t === "installation" ? "invalid_installation_anchor" : "invalid_zone_anchor"
    )}</span>` : d}
      </label>
    `;
  }
};
j.styles = ae, j.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 }
};
let V = j;
class oe extends V {
  render() {
    return !this.hass || !this._config ? d : c`
      <div class="editor">
        <section>${this.anchorSelector("installation")}</section>
      </div>
    `;
  }
}
class le extends V {
  render() {
    return !this.hass || !this._config ? d : c`
      <div class="editor">
        <section>${this.anchorSelector("zone")}</section>
      </div>
    `;
  }
}
const W = class W extends b {
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
    return c`<div class="metric"><span>${t}</span><strong>${C(this.hass, e)}</strong></div>`;
  }
  async call(t, e, i = {}) {
    if (e && !window.confirm(e)) return;
    const r = J(this.hass, this._config), n = g(this.hass, r.status_entity), o = A(n, "config_entry_id");
    if (!o) {
      this._error = a(this.hass, "configuration_error");
      return;
    }
    this._busy = !0, this._error = void 0;
    try {
      await this.hass.callService(S, t, { config_entry_id: o, ...i });
    } catch (u) {
      this._error = `${a(this.hass, "action_failed")}: ${B(u)}`;
    } finally {
      this._busy = !1;
    }
  }
  async openOrders() {
    const t = J(this.hass, this._config), e = A(g(this.hass, t.status_entity), "config_entry_id");
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
        ), r = zt(i);
        this._orders = r.orders ?? [];
      } catch (i) {
        this._error = `${a(this.hass, "action_failed")}: ${B(i)}`;
      } finally {
        this._busy = !1;
      }
    }
  }
  target(t) {
    return `${String(t.target_value)} ${t.target_type === "volume" ? a(this.hass, "liters") : a(this.hass, "seconds")}`;
  }
  dateKey(t) {
    const e = t instanceof Date ? t : new Date(t), i = new Intl.DateTimeFormat("en", {
      timeZone: this.hass.config?.time_zone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit"
    }).formatToParts(e), r = (n) => i.find((o) => o.type === n)?.value ?? "";
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
    return t === this.dateKey(/* @__PURE__ */ new Date()) ? `${a(this.hass, "today")}, ${e}` : e;
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
    if (!this.hass || !this._config) return d;
    if (!this._config.entity)
      return c`<ha-card><div class="card"><div class="warning" role="alert"><ha-icon icon="mdi:water-outline"></ha-icon><span>${a(this.hass, "select_installation")}</span></div></div></ha-card>`;
    if (!K(g(this.hass, this._config.entity), "installation"))
      return c`<ha-card><div class="card"><div class="warning danger" role="alert"><ha-icon icon="mdi:water-alert"></ha-icon><span>${a(this.hass, "invalid_installation_anchor")}</span></div></div></ha-card>`;
    const t = J(this.hass, this._config);
    if (!t.status_entity || !g(this.hass, t.status_entity))
      return c`<ha-card><div class="card"><div class="warning"><ha-icon icon="mdi:water-alert"></ha-icon><span>${a(this.hass, "missing")}</span></div></div></ha-card>`;
    const e = g(this.hass, t.status_entity), i = A(e, "config_entry_id"), r = e?.state ?? "unavailable", n = e?.attributes.volume_control_available === !0, o = typeof e?.attributes.card_name == "string" ? e.attributes.card_name : e?.attributes.friendly_name ?? a(this.hass, "overview"), u = this.ordersForSelectedDate(), h = this.nextOrdersDate();
    return c`
      <ha-card>
        <div class="card">
          <header>
            <div class="hero">
              <ha-icon .icon=${Mt(r)}></ha-icon>
              <div>
                <h2>${o}</h2>
                <strong>${re(e) ? O(this.hass, e.state) : C(this.hass, e)}</strong>
              </div>
            </div>
          </header>

          <div class="metrics">
            <button class="metric metric-button" data-testid="open-orders" ?disabled=${this._busy || !i} @click=${this.openOrders}><span>${a(this.hass, "pending")}</span><strong>${C(this.hass, g(this.hass, t.pending_entity))}</strong></button>
            ${this.metric(a(this.hass, "next_zone"), g(this.hass, t.next_entity))}
            ${this.metric(a(this.hass, "expected_start"), g(this.hass, t.next_start_entity))}
            ${this.metric(a(this.hass, n ? "water_today" : "runtime_today"), g(this.hass, n ? t.today_consumption_entity : t.runtime_today_entity))}
            ${this.metric(a(this.hass, n ? "water_month" : "runtime_month"), g(this.hass, n ? t.month_consumption_entity : t.runtime_month_entity))}
            ${n ? this.metric(a(this.hass, "physical_meter"), g(this.hass, t.physical_meter_entity)) : d}
          </div>

          ${this._error ? c`<div class="error" role="alert">${this._error}</div>` : d}
          <div class="actions">
            <button class="danger emergency" data-testid="emergency-stop" ?disabled=${this._busy || !i} @click=${() => this.call("emergency_stop")}><ha-icon icon="mdi:alert-octagon-outline"></ha-icon>${a(this.hass, "emergency")}</button>
          </div>
          ${this._ordersOpen ? c`
            <dialog open aria-labelledby="orders-title">
              <div class="dialog-header"><h2 id="orders-title">${a(this.hass, "irrigation_orders")}</h2><button class="icon-button" aria-label=${a(this.hass, "close")} @click=${() => {
      this._ordersOpen = !1;
    }}>×</button></div>
              <div class="date-navigation">
                <button class="icon-button" aria-label=${a(this.hass, "previous_day")} @click=${() => this.shiftOrdersDate(-1)}><ha-icon icon="mdi:chevron-left"></ha-icon></button>
                <label class="field"><span>${a(this.hass, "date")}</span><input data-testid="orders-date" type="date" .value=${this._ordersDate} @change=${(p) => {
      const l = p.target;
      this._ordersDate = l.value || this.dateKey(/* @__PURE__ */ new Date()), l.value = this._ordersDate;
    }} /></label>
                <button class="icon-button" aria-label=${a(this.hass, "next_day")} @click=${() => this.shiftOrdersDate(1)}><ha-icon icon="mdi:chevron-right"></ha-icon></button>
              </div>
              <h3 class="selected-date" aria-live="polite">${this.formatDate(this._ordersDate)}</h3>
              ${this._busy ? c`<p aria-live="polite">${a(this.hass, "loading")}</p>` : this._orders.length === 0 ? c`<p>${a(this.hass, "no_open_orders")}</p>` : u.length === 0 ? c`
                <div class="empty-day"><p>${a(this.hass, "no_orders_for_day")}</p>${h ? c`<button data-testid="next-orders-date" @click=${() => {
      this._ordersDate = h;
    }}>${a(this.hass, "next_orders_on")} ${this.formatDate(h)}</button>` : d}</div>` : c`
                <div class="order-list">
                  ${u.map((p) => c`<article><div><strong>${String(p.zone)}</strong><time datetime=${String(p.expected_start)}>${this.formatTime(p.expected_start)}</time></div><span>${O(this.hass, String(p.source))} · ${this.target(p)} · ${O(this.hass, String(p.status))}</span></article>`)}
                </div>`}
            </dialog>` : d}
        </div>
      </ha-card>
    `;
  }
};
W.styles = Ct, W.properties = {
  hass: { attribute: !1 },
  _config: { state: !0 },
  _busy: { state: !0 },
  _error: { state: !0 },
  _ordersOpen: { state: !0 },
  _orders: { state: !0 },
  _ordersDate: { state: !0 }
};
let tt = W;
function X(s, t) {
  return t == null ? "–" : O(s, String(t));
}
const F = class F extends b {
  constructor() {
    super(...arguments), this._targetMode = "duration", this._targetValue = 600, this._durationValue = "00:10:00", this._hardLimit = "01:00:00", this._busy = !1, this._manualOpen = !1, this._historyOpen = !1, this._conflictPolicy = "start_now", this._history = [], this._historyOffset = 0, this._historyTotal = 0, this._historySource = "", this._historyResult = "";
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
    return c`<div class="metric"><span>${t}</span><strong>${C(this.hass, e)}</strong></div>`;
  }
  context() {
    const t = Q(this.hass, this._config), e = g(this.hass, t.zone_entity), i = A(e, "config_entry_id"), r = A(e, "zone_subentry_id");
    return i && r ? { config_entry_id: i, zone_subentry_id: r } : void 0;
  }
  async perform(t, e, i, r = !1) {
    if (!(i && !window.confirm(i))) {
      this._busy = !0, this._error = void 0;
      try {
        r ? await this.hass.callService(S, t, e, void 0, !1, !0) : await this.hass.callService(S, t, e);
      } catch (n) {
        this._error = `${a(this.hass, "action_failed")}: ${B(n)}`;
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
    const e = yt(this._durationValue), i = yt(this._hardLimit);
    if (this._targetMode === "duration" && e === void 0) {
      this._error = a(this.hass, "invalid_duration");
      return;
    }
    if (this._targetMode === "amount" && (!Number.isFinite(this._targetValue) || this._targetValue <= 0)) {
      this._error = a(this.hass, "invalid_target");
      return;
    }
    if (this._targetMode === "amount" && i === void 0) {
      this._error = a(this.hass, "hard_limit_required");
      return;
    }
    const r = g(this.hass, Q(this.hass, this._config).zone_entity), n = this._targetMode === "duration" ? U(r, "max_manual_duration_seconds") : U(r, "max_manual_volume_runtime_seconds"), o = this._targetMode === "duration" ? e : i;
    if (o === void 0) return;
    if (n !== void 0 && o > n) {
      this._error = a(this.hass, "invalid_target");
      return;
    }
    const u = this._targetMode === "duration" ? { duration: e } : { amount: this._targetValue, hard_time_limit: i }, h = r?.attributes.active_execution === !0;
    await this.perform("start_manual_from_card", {
      ...t,
      ...u,
      conflict_policy: h ? this._conflictPolicy : "start_now"
    }, void 0, !0), this._error || (this._manualOpen = !1);
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
        const r = await this.hass.callService(
          S,
          "list_zone_history",
          i,
          void 0,
          !1,
          !0
        ), n = zt(r);
        this._history = n.items ?? [], this._historyOffset = n.offset ?? t, this._historyTotal = n.total ?? 0;
      } catch (i) {
        this._error = `${a(this.hass, "action_failed")}: ${B(i)}`;
      } finally {
        this._busy = !1;
      }
    }
  }
  historyTarget(t) {
    return `${String(t.target_value)} ${t.target_type === "volume" ? a(this.hass, "liters") : a(this.hass, "seconds")}`;
  }
  render() {
    if (!this.hass || !this._config) return d;
    if (!this._config.entity)
      return c`<ha-card><div class="card"><div class="warning" role="alert"><ha-icon icon="mdi:water-outline"></ha-icon><span>${a(this.hass, "select_zone")}</span></div></div></ha-card>`;
    if (!K(g(this.hass, this._config.entity), "zone"))
      return c`<ha-card><div class="card"><div class="warning danger" role="alert"><ha-icon icon="mdi:water-alert"></ha-icon><span>${a(this.hass, "invalid_zone_anchor")}</span></div></div></ha-card>`;
    const t = Q(this.hass, this._config);
    if (!t.zone_entity || !g(this.hass, t.zone_entity))
      return c`<ha-card><div class="card"><div class="warning"><ha-icon icon="mdi:water-alert"></ha-icon><span>${a(this.hass, "missing")}</span></div></div></ha-card>`;
    const e = g(this.hass, t.zone_entity), i = g(this.hass, t.status_entity), r = this.context(), n = A(e, "active_execution_id"), o = typeof e?.attributes.card_name == "string" ? e.attributes.card_name : e?.attributes.friendly_name ?? a(this.hass, "zone"), u = ["disabled", "installation_disabled", "safety_lock", "needs_reconfiguration"].includes(
      i?.state ?? ""
    ), h = U(e, "max_manual_duration_seconds") ?? 604800, p = U(e, "max_manual_volume_runtime_seconds") ?? 604800;
    return c`
      <ha-card>
        <div class="card">
          <header>
            <div class="hero">
              <ha-icon .icon=${Mt(i?.state ?? "unknown")}></ha-icon>
              <div>
                <h2>${o}</h2>
                <strong>${C(this.hass, i)}</strong>
              </div>
            </div>
          </header>

          <div class="metrics">
            ${this.metric(a(this.hass, "status"), i)}
            ${this.metric(a(this.hass, e?.attributes.volume_control_available === !0 ? "water_today" : "runtime_today"), g(this.hass, e?.attributes.volume_control_available === !0 ? t.water_today_entity : t.runtime_today_entity))}
            ${this.metric(a(this.hass, e?.attributes.volume_control_available === !0 ? "water_month" : "runtime_month"), g(this.hass, e?.attributes.volume_control_available === !0 ? t.water_month_entity : t.runtime_month_entity))}
            ${this.metric(a(this.hass, "next"), g(this.hass, t.next_irrigation_entity))}
          </div>

          ${this._error ? c`<div class="error" role="alert">${this._error}</div>` : d}
          <div class="actions">
            <button class="primary" data-testid="manual-irrigation" ?disabled=${this._busy || u || !r} @click=${() => this.openManual(e)}><ha-icon icon="mdi:sprinkler-variant"></ha-icon>${a(this.hass, "manual_water")}</button>
            ${i?.state === "watering" && n && r ? c`<button class="danger" data-testid="stop-watering" ?disabled=${this._busy} @click=${() => this.perform("stop", { config_entry_id: r.config_entry_id, execution_id: n }, a(this.hass, "confirm_stop_watering"))}><ha-icon icon="mdi:stop-circle-outline"></ha-icon>${a(this.hass, "stop_watering")}</button>` : d}
            <button data-testid="show-history" ?disabled=${this._busy || !r} @click=${() => this.loadHistory(0)}><ha-icon icon="mdi:history"></ha-icon>${a(this.hass, "show_history")}</button>
          </div>
          ${this._manualOpen ? c`
            <dialog open aria-labelledby="manual-title">
              <div class="dialog-header"><h2 id="manual-title">${a(this.hass, "manual_water")}</h2><button class="icon-button" aria-label=${a(this.hass, "close")} @click=${() => {
      this._manualOpen = !1;
    }}>×</button></div>
              <div class="form-grid">
                <label class="field"><span>${a(this.hass, "target")}</span><select data-testid="target-mode" .value=${this._targetMode} @change=${(l) => {
      this._targetMode = l.target.value;
    }}><option value="duration">${a(this.hass, "duration_mode")}</option>${e?.attributes.volume_control_available === !0 ? c`<option value="amount">${a(this.hass, "amount_mode")}</option>` : d}</select></label>
                <label class="field"><span>${this._targetMode === "duration" ? a(this.hass, "duration") : a(this.hass, "amount")}</span>${this._targetMode === "duration" ? c`<input data-testid="manual-target" type="text" placeholder="HH:MM:SS" pattern="[0-9]+:[0-5][0-9]:[0-5][0-9]([.][0-9]+)?" title=${`${a(this.hass, "maximum")}: ${vt(h)}`} .value=${this._durationValue} @input=${(l) => {
      this._durationValue = l.target.value;
    }} /><span>HH:MM:SS</span>` : c`<input data-testid="manual-target" type="number" min="0.001" max="1000000" step="0.1" .value=${String(this._targetValue)} @input=${(l) => {
      this._targetValue = Number(l.target.value);
    }} /><span>${a(this.hass, "liters")}</span>`}</label>
                ${this._targetMode === "amount" ? c`<label class="field"><span>${a(this.hass, "hard_limit")}</span><input data-testid="hard-limit" type="text" placeholder="HH:MM:SS" pattern="[0-9]+:[0-5][0-9]:[0-5][0-9]([.][0-9]+)?" title=${`${a(this.hass, "maximum")}: ${vt(p)}`} .value=${this._hardLimit} @input=${(l) => {
      this._hardLimit = l.target.value;
    }} /><span>HH:MM:SS</span></label>` : d}
                ${e?.attributes.active_execution === !0 ? c`<label class="field"><span>${a(this.hass, "active_execution_choice")}</span><select data-testid="conflict-policy" .value=${this._conflictPolicy} @change=${(l) => {
      this._conflictPolicy = l.target.value;
    }}><option value="stop_active">${a(this.hass, "stop_active_start_now")}</option><option value="priority_next">${a(this.hass, "finish_then_priority")}</option></select></label>` : d}
              </div>
              ${this._error ? c`<div class="error" role="alert">${this._error}</div>` : d}
              <div class="actions dialog-actions"><button data-testid="submit-manual" class="primary" ?disabled=${this._busy} @click=${this.request}>${a(this.hass, "start")}</button></div>
            </dialog>` : d}
          ${this._historyOpen ? c`
            <dialog open aria-labelledby="history-title">
              <div class="dialog-header"><h2 id="history-title">${a(this.hass, "irrigation_history")}</h2><button class="icon-button" aria-label=${a(this.hass, "close")} @click=${() => {
      this._historyOpen = !1;
    }}>×</button></div>
              <div class="filters"><label class="field"><span>${a(this.hass, "source")}</span><select .value=${this._historySource} @change=${(l) => {
      this._historySource = l.target.value, this.loadHistory(0);
    }}><option value="">${a(this.hass, "all")}</option><option value="manual">${a(this.hass, "manual")}</option><option value="automatic">${a(this.hass, "automatic")}</option></select></label><label class="field"><span>${a(this.hass, "result")}</span><select .value=${this._historyResult} @change=${(l) => {
      this._historyResult = l.target.value, this.loadHistory(0);
    }}><option value="">${a(this.hass, "all")}</option><option value="completed">${a(this.hass, "completed")}</option><option value="failed">${a(this.hass, "failed")}</option><option value="cancelled">${a(this.hass, "cancelled")}</option></select></label></div>
              ${this._busy ? c`<p aria-live="polite">${a(this.hass, "loading")}</p>` : c`<div class="history-list">${this._history.map((l) => c`<article><strong>${this.historyTarget(l)}</strong><span>${String(l.started_at)} – ${String(l.ended_at ?? "")}</span><span>${X(this.hass, l.source)} · ${X(this.hass, l.result)} · ${String(l.actual_duration)} s${l.actual_water == null ? "" : ` · ${String(l.actual_water)} L`} · ${X(this.hass, l.completion_reason)}</span></article>`)}</div>`}
              <div class="actions"><button ?disabled=${this._busy || this._historyOffset === 0} @click=${() => this.loadHistory(Math.max(0, this._historyOffset - 20))}>${a(this.hass, "previous")}</button><span>${this._historyTotal === 0 ? 0 : this._historyOffset + 1}–${Math.min(this._historyOffset + this._history.length, this._historyTotal)} / ${this._historyTotal}</span><button ?disabled=${this._busy || this._historyOffset + this._history.length >= this._historyTotal} @click=${() => this.loadHistory(this._historyOffset + 20)}>${a(this.hass, "next_page")}</button></div>
            </dialog>` : d}
        </div>
      </ha-card>
    `;
  }
};
F.styles = Ct, F.properties = {
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
let et = F;
const he = [
  ["irrigation-manager-overview-card", tt],
  ["irrigation-manager-zone-card", et],
  ["irrigation-manager-overview-card-editor", oe],
  ["irrigation-manager-zone-card-editor", le]
];
for (const [s, t] of he)
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
