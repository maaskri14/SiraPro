/* global Paddle, SIRAPRO_TIERS */
(function () {
  "use strict";

  var state = { billing: "month", totals: {}, country: null, email: null };

  function el(id) { return document.getElementById(id); }
  function isPlaceholder(id) { return !id || id.indexOf("REPLACEZ") !== -1; }

  function showBanner(msg, kind) {
    var b = el("config-banner");
    b.hidden = false;
    b.textContent = msg;
    b.className = "banner " + (kind || "warn");
  }

  function renderTiers() {
    var wrap = el("tiers");
    wrap.innerHTML = "";
    SIRAPRO_TIERS.forEach(function (tier) {
      var pid = tier.priceId[state.billing];
      var tot = state.totals[pid];
      var card = document.createElement("article");
      card.className = "tier" + (tier.name === "Pro" ? " featured" : "");

      var priceHtml;
      if (isPlaceholder(pid)) {
        priceHtml = '<div class="price">—</div><div class="per">price ID Paddle à configurer</div>';
      } else if (tot && tot.total) {
        // Affichage EXCLUSIF du formattedTotals renvoyé par Paddle.
        priceHtml = '<div class="price">' + tot.total + '</div><div class="per">' +
          (state.billing === "month" ? "/mois" : "/an") + '</div>';
      } else {
        priceHtml = '<div class="price">…</div><div class="per">chargement</div>';
      }

      card.innerHTML =
        "<h2>" + tier.name + "</h2>" +
        '<p class="desc">' + tier.description + "</p>" +
        priceHtml +
        "<ul>" + tier.features.map(function (f) { return "<li>" + f + "</li>"; }).join("") + "</ul>" +
        '<button class="subscribe" data-tier="' + tier.name + '"' +
        (isPlaceholder(pid) ? " disabled" : "") + ">S'abonner</button>";

      wrap.appendChild(card);
    });

    Array.prototype.forEach.call(wrap.querySelectorAll(".subscribe"), function (btn) {
      btn.addEventListener("click", function () { subscribe(btn.getAttribute("data-tier")); });
    });
  }

  function subscribe(name) {
    var tier = null;
    SIRAPRO_TIERS.forEach(function (t) { if (t.name === name) tier = t; });
    if (!tier) return;
    var pid = tier.priceId[state.billing];
    if (isPlaceholder(pid)) return;

    var args = {
      items: [{ priceId: pid, quantity: 1 }],
      settings: { displayMode: "overlay", variant: "one-page", theme: "light", locale: "fr" },
      onCheckoutCompleted: function () { window.location.href = "/welcome"; }
    };
    if (state.email) args.customer = { email: state.email };

    Paddle.Checkout.open(args);
  }

  function loadPrices() {
    var items = [];
    SIRAPRO_TIERS.forEach(function (t) {
      ["month", "year"].forEach(function (k) {
        if (!isPlaceholder(t.priceId[k])) items.push({ priceId: t.priceId[k], quantity: 1 });
      });
    });
    if (!items.length) { renderTiers(); return; }

    var args = { items: items };
    // Ne passer UN JAMAIS un sentinel interne à Paddle : seulement un vrai code ISO.
    if (state.country) args.address = { countryCode: state.country };

    Paddle.PricePreview(args).then(function (res) {
      var lines = (res && res.data && res.data.details && res.data.details.lineItems) || [];
      lines.forEach(function (li) {
        var pid = (li.item && li.item.priceId) || (li.price && li.price.id);
        if (pid && li.formattedTotals) state.totals[pid] = li.formattedTotals;
      });
      renderTiers();
    }).catch(function (err) {
      showBanner("Erreur PricePreview : " + (err && err.message ? err.message : err), "error");
      renderTiers();
    });
  }

  function setBilling(b) {
    state.billing = b;
    el("bill-month").className = b === "month" ? "on" : "";
    el("bill-year").className = b === "year" ? "on" : "";
    renderTiers();
  }

  function init() {
    try { state.email = localStorage.getItem("sirapro_email"); } catch (e) { state.email = null; }

    var hasPlaceholder = SIRAPRO_TIERS.some(function (t) {
      return isPlaceholder(t.priceId.month) || isPlaceholder(t.priceId.year);
    });
    if (hasPlaceholder) {
      showBanner("Complétez static/pricing-config.js avec vos price IDs Paddle (Starter et Advanced).");
    }

    if (typeof Paddle === "undefined") {
      showBanner("Paddle JS n'a pas pu être chargé (CDN bloqué ?).", "error");
      renderTiers();
      return;
    }

    fetch("/api/paddle/config").then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
        return j;
      });
    }).then(function (cfg) {
      Paddle.Setup({ token: cfg.client_token });
      return fetch("/api/country").then(function (r) { return r.json(); }).catch(function () { return { country: null }; });
    }).then(function (geo) {
      state.country = (geo && geo.country) || null;
      loadPrices();
    }).catch(function (err) {
      showBanner("Configuration Paddle impossible : " + err.message, "error");
      renderTiers();
    });

    el("bill-month").addEventListener("click", function () { setBilling("month"); });
    el("bill-year").addEventListener("click", function () { setBilling("year"); });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
