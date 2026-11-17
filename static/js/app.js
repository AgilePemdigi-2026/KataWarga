/* ==========================================================================
   KataWarga — shared UI behaviour
   No dependencies. Every interaction is progressive enhancement: pages stay
   usable when JavaScript is disabled.
   ========================================================================== */
(function () {
    "use strict";

    var THEME_KEY = "kw-theme";
    var doc = document.documentElement;

    function safeStorageGet(key) {
        try {
            return window.localStorage.getItem(key);
        } catch (error) {
            return null;
        }
    }

    function safeStorageSet(key, value) {
        try {
            window.localStorage.setItem(key, value);
        } catch (error) {
            /* Storage can be disabled; the theme still works for this page. */
        }
    }

    function currentTheme() {
        return doc.classList.contains("light") ? "light" : "dark";
    }

    function syncThemeControls(theme) {
        document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
            var isLight = theme === "light";
            button.setAttribute("aria-label", isLight ? "Aktifkan mode gelap" : "Aktifkan mode terang");
            button.setAttribute("title", isLight ? "Mode gelap" : "Mode terang");
            button.setAttribute("aria-pressed", String(isLight));
        });

        document.querySelectorAll("[data-theme-option]").forEach(function (option) {
            option.setAttribute("aria-pressed", String(option.dataset.themeOption === theme));
        });

        var themeMeta = document.querySelector('meta[name="theme-color"]');
        if (themeMeta) {
            themeMeta.setAttribute("content", theme === "light" ? "#f4f6fb" : "#0f172b");
        }

        document.querySelectorAll("[data-theme-label]").forEach(function (label) {
            label.textContent = theme === "light" ? "Mode terang" : "Mode gelap";
        });
    }

    function applyTheme(theme) {
        var next = theme === "light" ? "light" : "dark";
        doc.classList.remove("light", "dark");
        doc.classList.add(next);
        safeStorageSet(THEME_KEY, next);
        syncThemeControls(next);
        document.dispatchEvent(new CustomEvent("kw:themechange", { detail: { theme: next } }));
    }

    function initTheme() {
        var stored = safeStorageGet(THEME_KEY);
        var initial = stored === "light" || stored === "dark" ? stored : "dark";
        if (!doc.classList.contains(initial)) {
            doc.classList.remove("light", "dark");
            doc.classList.add(initial);
        }
        syncThemeControls(initial);

        document.addEventListener("click", function (event) {
            var toggle = event.target.closest("[data-theme-toggle]");
            if (toggle) {
                event.preventDefault();
                applyTheme(currentTheme() === "light" ? "dark" : "light");
                return;
            }

            var option = event.target.closest("[data-theme-option]");
            if (option) {
                event.preventDefault();
                applyTheme(option.dataset.themeOption);
            }
        });
    }

    /* ---------------------------------------------------------------------
       Dropdowns (notifications, profile)
       --------------------------------------------------------------------- */
    function closeDropdown(dropdown, restoreFocus) {
        var trigger = dropdown.querySelector("[data-dropdown-trigger]");
        var panel = dropdown.querySelector("[data-dropdown-panel]");
        if (!panel || panel.hidden) return;
        panel.hidden = true;
        if (trigger) {
            trigger.setAttribute("aria-expanded", "false");
            if (restoreFocus) trigger.focus();
        }
    }

    function closeAllDropdowns(except) {
        document.querySelectorAll("[data-dropdown].is-open").forEach(function (dropdown) {
            if (dropdown !== except) {
                dropdown.classList.remove("is-open");
                closeDropdown(dropdown, false);
            }
        });
    }

    function initDropdowns() {
        document.querySelectorAll("[data-dropdown]").forEach(function (dropdown) {
            var trigger = dropdown.querySelector("[data-dropdown-trigger]");
            var panel = dropdown.querySelector("[data-dropdown-panel]");
            if (!trigger || !panel) return;

            panel.hidden = true;
            trigger.setAttribute("aria-expanded", "false");
            trigger.setAttribute("aria-haspopup", "true");

            trigger.addEventListener("click", function (event) {
                event.preventDefault();
                var willOpen = panel.hidden;
                closeAllDropdowns(dropdown);
                panel.hidden = !willOpen;
                trigger.setAttribute("aria-expanded", String(willOpen));
                dropdown.classList.toggle("is-open", willOpen);
                if (willOpen) {
                    var firstItem = panel.querySelector("a, button, input");
                    if (firstItem && event.detail !== 0) firstItem.focus({ preventScroll: true });
                }
            });

            panel.addEventListener("keydown", function (event) {
                if (event.key === "Escape") {
                    event.preventDefault();
                    dropdown.classList.remove("is-open");
                    closeDropdown(dropdown, true);
                }
            });
        });

        document.addEventListener("click", function (event) {
            if (!event.target.closest("[data-dropdown]")) closeAllDropdowns(null);
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape") closeAllDropdowns(null);
        });
    }

    /* ---------------------------------------------------------------------
       Mobile sidebar
       --------------------------------------------------------------------- */
    function initSidebar() {
        var sidebar = document.getElementById("kw-sidebar");
        if (!sidebar) return;

        var overlay = document.querySelector("[data-sidebar-overlay]");
        var openers = document.querySelectorAll("[data-sidebar-open]");
        var closers = document.querySelectorAll("[data-sidebar-close]");
        var lastFocused = null;

        function focusable() {
            return Array.prototype.slice
                .call(sidebar.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'))
                .filter(function (element) {
                    return element.offsetParent !== null;
                });
        }

        function open() {
            lastFocused = document.activeElement;
            sidebar.classList.add("is-open");
            if (overlay) overlay.classList.add("is-open");
            document.body.style.overflow = "hidden";
            openers.forEach(function (button) {
                button.setAttribute("aria-expanded", "true");
            });
            var first = sidebar.querySelector("[data-sidebar-close]") || focusable()[0];
            if (first) first.focus();
        }

        function close() {
            sidebar.classList.remove("is-open");
            if (overlay) overlay.classList.remove("is-open");
            document.body.style.overflow = "";
            openers.forEach(function (button) {
                button.setAttribute("aria-expanded", "false");
            });
            if (lastFocused && typeof lastFocused.focus === "function") lastFocused.focus();
        }

        openers.forEach(function (button) {
            button.addEventListener("click", function (event) {
                event.preventDefault();
                open();
            });
        });

        closers.forEach(function (button) {
            button.addEventListener("click", close);
        });

        if (overlay) overlay.addEventListener("click", close);

        document.addEventListener("keydown", function (event) {
            if (!sidebar.classList.contains("is-open")) return;
            if (event.key === "Escape") {
                event.preventDefault();
                close();
                return;
            }
            if (event.key !== "Tab") return;

            var items = focusable();
            if (!items.length) return;
            var first = items[0];
            var last = items[items.length - 1];

            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        });

        window.addEventListener("resize", function () {
            if (window.innerWidth >= 1024 && sidebar.classList.contains("is-open")) close();
        });
    }

    /* ---------------------------------------------------------------------
       Modals
       --------------------------------------------------------------------- */
    function initModals() {
        var lastFocused = null;

        function closeModal(modal, restoreFocus) {
            if (!modal) return;
            modal.classList.remove("is-open");
            modal.setAttribute("aria-hidden", "true");
            document.body.style.overflow = "";
            if (restoreFocus && lastFocused) lastFocused.focus();
        }

        function openModal(modal) {
            if (!modal) return;
            lastFocused = document.activeElement;
            closeAllDropdowns(null);
            modal.classList.add("is-open");
            modal.setAttribute("aria-hidden", "false");
            document.body.style.overflow = "hidden";
            var target = modal.querySelector("[data-modal-autofocus]") || modal.querySelector(".kw-modal__panel");
            if (target) {
                if (!target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
                target.focus({ preventScroll: true });
            }
        }

        document.querySelectorAll("[data-modal-open]").forEach(function (trigger) {
            trigger.addEventListener("click", function (event) {
                event.preventDefault();
                openModal(document.getElementById(trigger.dataset.modalOpen));
            });
        });

        document.querySelectorAll(".kw-modal").forEach(function (modal) {
            modal.querySelectorAll("[data-modal-close]").forEach(function (button) {
                button.addEventListener("click", function (event) {
                    event.preventDefault();
                    closeModal(modal, true);
                });
            });

            modal.addEventListener("click", function (event) {
                if (event.target.matches(".kw-modal__backdrop")) closeModal(modal, true);
            });

            modal.addEventListener("keydown", function (event) {
                if (event.key === "Escape") {
                    event.preventDefault();
                    closeModal(modal, true);
                    return;
                }
                if (event.key !== "Tab") return;

                var items = Array.prototype.slice
                    .call(modal.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'))
                    .filter(function (element) {
                        return element.offsetParent !== null;
                    });
                if (!items.length) return;
                var first = items[0];
                var last = items[items.length - 1];
                if (event.shiftKey && document.activeElement === first) {
                    event.preventDefault();
                    last.focus();
                } else if (!event.shiftKey && document.activeElement === last) {
                    event.preventDefault();
                    first.focus();
                }
            });
        });

        document.querySelectorAll("[data-open-modal-on-load]").forEach(function (node) {
            openModal(document.getElementById(node.dataset.openModalOnLoad));
        });
    }

    /* ---------------------------------------------------------------------
       Toasts
       --------------------------------------------------------------------- */
    function initToasts() {
        var stack = document.querySelector("[data-toasts]");
        if (!stack) return;

        stack.querySelectorAll("[data-toast]").forEach(function (toast, index) {
            var close = toast.querySelector("[data-toast-close]");
            var remove = function () {
                toast.classList.add("is-leaving");
                window.setTimeout(function () {
                    toast.remove();
                    if (!stack.querySelector("[data-toast]")) stack.hidden = true;
                }, 150);
            };

            if (close) close.addEventListener("click", remove);

            if (!toast.classList.contains("kw-toast--error")) {
                window.setTimeout(remove, 6500 + index * 400);
            }
        });
    }

    /* ---------------------------------------------------------------------
       Forms: confirmation, genuine loading feedback, auto-submit
       --------------------------------------------------------------------- */
    function initForms() {
        document.addEventListener("submit", function (event) {
            var form = event.target;
            if (!(form instanceof HTMLFormElement)) return;

            var confirmMessage = form.dataset.confirm;
            if (confirmMessage && !window.confirm(confirmMessage)) {
                event.preventDefault();
                return;
            }

            if (form.method.toLowerCase() !== "post" || form.dataset.loading === "off") return;

            var submitter = event.submitter || form.querySelector('button[type="submit"], input[type="submit"]');
            if (!submitter || submitter.disabled) return;

            if (!submitter.dataset.originalHtml) {
                submitter.dataset.originalHtml = submitter.innerHTML;
            }

            if (submitter.tagName === "INPUT") {
                submitter.value = "Memproses…";
            } else {
                submitter.innerHTML = '<span class="kw-spinner" aria-hidden="true"></span><span>Memproses…</span>';
            }
            submitter.classList.add("is-loading");
            submitter.setAttribute("aria-busy", "true");
            submitter.disabled = true;

            /* Enable again for bfcache restores and for HTMX responses that
               keep the current DOM. No fake delay is introduced. */
            window.setTimeout(function () {
                if (!document.body.contains(submitter)) return;
                submitter.disabled = false;
                submitter.classList.remove("is-loading");
                submitter.removeAttribute("aria-busy");
                submitter.innerHTML = submitter.dataset.originalHtml;
            }, 12000);
        });

        document.querySelectorAll("[data-auto-submit]").forEach(function (control) {
            control.addEventListener("change", function () {
                if (control.form) control.form.requestSubmit();
            });
        });

        window.addEventListener("pageshow", function () {
            document.querySelectorAll(".kw-btn.is-loading").forEach(function (button) {
                if (button.dataset.originalHtml) button.innerHTML = button.dataset.originalHtml;
                button.classList.remove("is-loading");
                button.disabled = false;
            });
        });
    }

    /* ---------------------------------------------------------------------
       Kanban columns as tabs on small screens
       --------------------------------------------------------------------- */
    function initBoardTabs() {
        var tablist = document.querySelector("[data-board-tabs]");
        if (!tablist) return;

        var tabs = Array.prototype.slice.call(tablist.querySelectorAll("[data-board-tab]"));
        var columns = Array.prototype.slice.call(document.querySelectorAll("[data-board-col]"));

        function activate(key, moveFocus) {
            tabs.forEach(function (tab) {
                var isActive = tab.dataset.boardTab === key;
                tab.setAttribute("aria-selected", String(isActive));
                tab.setAttribute("tabindex", isActive ? "0" : "-1");
                if (isActive && moveFocus) tab.focus();
            });
            columns.forEach(function (column) {
                column.classList.toggle("is-active", column.dataset.boardCol === key);
            });
        }

        tabs.forEach(function (tab, index) {
            tab.addEventListener("click", function () {
                activate(tab.dataset.boardTab, false);
            });
            tab.addEventListener("keydown", function (event) {
                if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
                event.preventDefault();
                var next = index;
                if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
                if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
                if (event.key === "Home") next = 0;
                if (event.key === "End") next = tabs.length - 1;
                activate(tabs[next].dataset.boardTab, true);
            });
        });

        if (tabs.length) activate(tabs[0].dataset.boardTab, false);
    }

    /* ---------------------------------------------------------------------
       Dependency-free line chart
       --------------------------------------------------------------------- */
    function buildSvgElement(name, attributes) {
        var element = document.createElementNS("http://www.w3.org/2000/svg", name);
        Object.keys(attributes || {}).forEach(function (key) {
            element.setAttribute(key, attributes[key]);
        });
        return element;
    }

    function initCharts() {
        document.querySelectorAll("[data-chart-source]").forEach(function (container) {
            var source = document.getElementById(container.dataset.chartSource);
            if (!source) return;

            var payload;
            try {
                payload = JSON.parse(source.textContent);
            } catch (error) {
                return;
            }

            var labels = payload.labels || [];
            var series = payload.series || [];
            if (!labels.length || !series.length) return;

            var width = 720;
            var height = 260;
            var padding = { top: 18, right: 30, bottom: 30, left: 38 };
            var plotWidth = width - padding.left - padding.right;
            var plotHeight = height - padding.top - padding.bottom;
            var maxValue = Number(payload.max_value || 0);

            series.forEach(function (item) {
                item.values.forEach(function (value) {
                    maxValue = Math.max(maxValue, Number(value) || 0);
                });
            });
            if (maxValue <= 0) maxValue = 1;

            var primarySeries = series[0];
            var primaryMax = Number(primarySeries.max || maxValue) || 1;
            var secondarySeries = series.length > 1 ? series[1] : null;
            var secondaryMax = secondarySeries
                ? Number(secondarySeries.max || maxValue) || 1
                : 1;

            var svg = buildSvgElement("svg", {
                viewBox: "0 0 " + width + " " + height,
                role: "img",
                "aria-label": payload.aria_label || "Grafik tren bulanan"
            });

            for (var tick = 0; tick <= 4; tick += 1) {
                var y = padding.top + (plotHeight / 4) * tick;
                svg.appendChild(buildSvgElement("line", {
                    x1: padding.left,
                    x2: width - padding.right,
                    y1: y,
                    y2: y,
                    class: "kw-chart-grid"
                }));

                var label = buildSvgElement("text", {
                    x: padding.left - 9,
                    y: y + 3,
                    "text-anchor": "end",
                    class: "kw-chart-axis"
                });
                label.textContent = String(Math.round(primaryMax - (primaryMax / 4) * tick));
                svg.appendChild(label);

                if (secondarySeries && secondaryMax !== primaryMax) {
                    var secondaryLabel = buildSvgElement("text", {
                        x: width - padding.right + 7,
                        y: y + 3,
                        "text-anchor": "start",
                        class: "kw-chart-axis"
                    });
                    secondaryLabel.textContent = String(Math.round(secondaryMax - (secondaryMax / 4) * tick));
                    svg.appendChild(secondaryLabel);
                }
            }

            var step = labels.length > 1 ? plotWidth / (labels.length - 1) : 0;
            labels.forEach(function (labelText, index) {
                var x = padding.left + step * index;
                var label = buildSvgElement("text", {
                    x: x,
                    y: height - 8,
                    "text-anchor": "middle",
                    class: "kw-chart-axis"
                });
                label.textContent = labelText;
                svg.appendChild(label);
            });

            var tooltips = [];

            series.forEach(function (item) {
                var itemMax = Number(item.max || maxValue) || 1;
                var points = item.values.map(function (value, index) {
                    var x = padding.left + (labels.length > 1 ? step * index : plotWidth / 2);
                    var y = padding.top + plotHeight - (Number(value) / itemMax) * plotHeight;
                    return { x: x, y: y, value: Number(value) };
                });

                if (points.length > 1) {
                    var line = points.map(function (point) { return point.x + "," + point.y; }).join(" ");
                    svg.appendChild(buildSvgElement("polyline", {
                        points: line,
                        class: "kw-chart-line",
                        style: "stroke:" + item.color
                    }));
                }

                points.forEach(function (point, index) {
                    var circle = buildSvgElement("circle", {
                        cx: point.x,
                        cy: point.y,
                        r: 4,
                        class: "kw-chart-point",
                        style: "fill:" + item.color,
                        tabindex: "0",
                        role: "img",
                        "aria-label": labels[index] + ": " + point.value + " " + (item.unit || "")
                    });

                    var tooltip = document.createElement("div");
                    tooltip.className = "kw-chart-tooltip";
                    tooltip.hidden = true;
                    tooltip.innerHTML = "<strong>" + labels[index] + "</strong><br>" +
                        series.map(function (entry) {
                            return entry.name + ": " + entry.values[index] + (entry.unit ? " " + entry.unit : "");
                        }).join("<br>");

                    function showTooltip() {
                        tooltip.hidden = false;
                        tooltip.style.left = (point.x / width) * 100 + "%";
                        tooltip.style.top = (point.y / height) * 100 + "%";
                    }

                    function hideTooltip() {
                        tooltip.hidden = true;
                    }

                    circle.addEventListener("mouseenter", showTooltip);
                    circle.addEventListener("mouseleave", hideTooltip);
                    circle.addEventListener("focus", showTooltip);
                    circle.addEventListener("blur", hideTooltip);
                    svg.appendChild(circle);
                    tooltips.push(tooltip);
                });
            });

            container.innerHTML = "";
            container.appendChild(svg);
            tooltips.forEach(function (tooltip) {
                container.appendChild(tooltip);
            });
        });
    }

    /* ---------------------------------------------------------------------
       CSV file picker
       --------------------------------------------------------------------- */
    function initFileDrops() {
        document.querySelectorAll("[data-file-drop]").forEach(function (drop) {
            var input = drop.querySelector('input[type="file"]');
            var nameNode = drop.querySelector("[data-file-name]");
            var metaNode = drop.querySelector("[data-file-meta]");
            var errorNode = drop.querySelector("[data-file-error]");
            if (!input) return;

            function formatSize(bytes) {
                if (bytes < 1024) return bytes + " B";
                if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
                return (bytes / (1024 * 1024)).toFixed(2) + " MB";
            }

            function validate() {
                var file = input.files && input.files[0];
                if (!file) {
                    if (nameNode) nameNode.textContent = "Belum ada file dipilih";
                    if (metaNode) metaNode.textContent = "CSV maksimal 5 MB dan 2.000 baris.";
                    if (errorNode) {
                        errorNode.hidden = true;
                        errorNode.textContent = "";
                    }
                    input.setCustomValidity("");
                    return true;
                }

                var error = "";
                if (!/\.csv$/i.test(file.name)) {
                    error = "Format file harus .csv.";
                } else if (file.size > 5 * 1024 * 1024) {
                    error = "Ukuran file melebihi 5 MB.";
                }

                if (nameNode) nameNode.textContent = file.name;
                if (metaNode) metaNode.textContent = formatSize(file.size);
                if (errorNode) {
                    errorNode.hidden = !error;
                    errorNode.textContent = error;
                }
                input.setCustomValidity(error);
                return !error;
            }

            input.addEventListener("change", validate);

            drop.addEventListener("click", function (event) {
                if (event.target === input) return;
                event.preventDefault();
                input.click();
            });

            ["dragenter", "dragover"].forEach(function (name) {
                drop.addEventListener(name, function (event) {
                    event.preventDefault();
                    drop.classList.add("is-dragging");
                });
            });

            ["dragleave", "drop"].forEach(function (name) {
                drop.addEventListener(name, function (event) {
                    event.preventDefault();
                    drop.classList.remove("is-dragging");
                });
            });

            drop.addEventListener("drop", function (event) {
                if (!event.dataTransfer || !event.dataTransfer.files.length) return;
                input.files = event.dataTransfer.files;
                validate();
            });

            validate();
        });
    }

    /* ---------------------------------------------------------------------
       Misc: password visibility, keyboard search shortcut, active query clear
       --------------------------------------------------------------------- */
    function initPasswordToggles() {
        document.querySelectorAll("[data-toggle-password]").forEach(function (button) {
            button.addEventListener("click", function () {
                var input = document.getElementById(button.dataset.togglePassword);
                if (!input) return;
                var isHidden = input.type === "password";
                input.type = isHidden ? "text" : "password";
                button.textContent = isHidden ? "Sembunyikan" : "Tampilkan";
                button.setAttribute("aria-label", isHidden ? "Sembunyikan kata sandi" : "Tampilkan kata sandi");
                button.setAttribute("aria-pressed", String(isHidden));
            });
        });
    }

    function initSearchShortcuts() {
        var searchInput = document.getElementById("global-search");
        if (!searchInput) return;

        document.addEventListener("keydown", function (event) {
            var tag = (event.target.tagName || "").toLowerCase();
            var isTyping = tag === "input" || tag === "textarea" || tag === "select" || event.target.isContentEditable;
            if (isTyping) return;

            if (event.key === "/" || ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k")) {
                if (searchInput.offsetParent === null) return;
                event.preventDefault();
                searchInput.focus();
                searchInput.select();
            }
        });
    }

    function initHtmxIntegration() {
        if (!window.htmx) return;

        document.body.addEventListener("htmx:beforeRequest", function (event) {
            var indicator = event.detail.elt.querySelector("[data-htmx-indicator]");
            if (indicator) indicator.hidden = false;
        });

        document.body.addEventListener("htmx:afterRequest", function (event) {
            var indicator = event.detail.elt.querySelector("[data-htmx-indicator]");
            if (indicator) indicator.hidden = true;
        });
    }

    function boot() {
        initTheme();
        initDropdowns();
        initSidebar();
        initModals();
        initToasts();
        initForms();
        initBoardTabs();
        initCharts();
        initFileDrops();
        initPasswordToggles();
        initSearchShortcuts();
        initHtmxIntegration();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }
})();
