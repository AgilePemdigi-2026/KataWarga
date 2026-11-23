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
                    return;
                }

                if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;

                var items = Array.prototype.slice
                    .call(panel.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])'))
                    .filter(function (element) {
                        return element.offsetParent !== null;
                    });
                if (!items.length) return;

                event.preventDefault();
                var currentIndex = items.indexOf(document.activeElement);
                var nextIndex;

                if (event.key === "ArrowDown") {
                    nextIndex = currentIndex < 0 ? 0 : (currentIndex + 1) % items.length;
                } else {
                    nextIndex = currentIndex < 0 ? items.length - 1 : (currentIndex - 1 + items.length) % items.length;
                }
                items[nextIndex].focus();
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
            var timer = null;

            var remove = function () {
                if (timer) window.clearTimeout(timer);
                timer = null;
                toast.classList.add("is-leaving");
                window.setTimeout(function () {
                    toast.remove();
                    if (!stack.querySelector("[data-toast]")) stack.hidden = true;
                }, 150);
            };

            var schedule = function () {
                if (timer || toast.classList.contains("kw-toast--error")) return;
                timer = window.setTimeout(remove, 6500 + index * 400);
            };

            var pause = function () {
                if (!timer) return;
                window.clearTimeout(timer);
                timer = null;
            };

            if (close) close.addEventListener("click", remove);

            toast.addEventListener("mouseenter", pause);
            toast.addEventListener("mouseleave", schedule);
            toast.addEventListener("focusin", pause);
            toast.addEventListener("focusout", function (event) {
                if (!toast.contains(event.relatedTarget)) schedule();
            });

            schedule();
        });
    }

    /* ---------------------------------------------------------------------
       Forms: confirmation, genuine loading feedback, auto-submit
       --------------------------------------------------------------------- */
    function restoreSubmitter(submitter) {
        if (!submitter) return;
        if (!document.body.contains(submitter)) return;

        // ONLY restore elements that were explicitly put into loading state by KataWarga
        // to avoid accidentally re-enabling buttons disabled by form validation, permissions, or business logic
        if (submitter.dataset.kwLoading !== "1") return;

        delete submitter.dataset.kwLoading;
        submitter.disabled = false;
        submitter.classList.remove("is-loading");
        submitter.removeAttribute("aria-busy");

        if (submitter.tagName === "INPUT") {
            if (typeof submitter.dataset.originalValue !== "undefined") {
                submitter.value = submitter.dataset.originalValue;
                delete submitter.dataset.originalValue;
            }
        } else {
            if (typeof submitter.dataset.originalHtml !== "undefined") {
                submitter.innerHTML = submitter.dataset.originalHtml;
                delete submitter.dataset.originalHtml;
            } else {
                var spinner = submitter.querySelector(".kw-spinner");
                if (spinner) spinner.remove();
            }
        }

        if (submitter.form) {
            delete submitter.form.dataset.kwSubmitting;
        }
    }

    function initForms() {
        var activeConfirm = null;

        function closeConfirm(confirmed) {
            if (!activeConfirm) return;

            var state = activeConfirm;
            activeConfirm = null;
            state.dialog.classList.remove("is-open");
            state.dialog.setAttribute("aria-hidden", "true");
            document.body.style.overflow = "";

            window.setTimeout(function () {
                if (state.dialog.parentNode) state.dialog.parentNode.removeChild(state.dialog);
            }, 160);

            if (confirmed) {
                state.form.dataset.kwConfirmed = "1";
                window.setTimeout(function () {
                    if (state.form.dataset.kwConfirmed === "1") {
                        delete state.form.dataset.kwConfirmed;
                    }
                }, 0);

                if (typeof state.form.requestSubmit === "function") {
                    if (state.submitter && state.submitter.form === state.form) {
                        state.form.requestSubmit(state.submitter);
                    } else {
                        state.form.requestSubmit();
                    }
                } else {
                    state.form.submit();
                }
                return;
            }

            if (state.previousFocus && typeof state.previousFocus.focus === "function") {
                state.previousFocus.focus({ preventScroll: true });
            }
        }

        function openConfirm(message, form, submitter) {
            if (activeConfirm) closeConfirm(false);

            var previousFocus = submitter || document.activeElement;
            var dialog = document.createElement("div");
            dialog.className = "kw-modal kw-confirm is-open";
            dialog.setAttribute("aria-hidden", "false");
            dialog.innerHTML = [
                '<div class="kw-modal__backdrop" data-confirm-cancel></div>',
                '<div class="kw-modal__panel kw-confirm__panel" role="alertdialog" aria-modal="true" aria-labelledby="kw-confirm-title" aria-describedby="kw-confirm-message" tabindex="-1">',
                '  <div class="kw-modal__head">',
                '    <div class="kw-inline" style="align-items:flex-start;gap:11px">',
                '      <span class="kw-confirm__icon" aria-hidden="true"><svg><use href="#icon-alert"></use></svg></span>',
                '      <div>',
                '        <h2 class="kw-modal__title" id="kw-confirm-title">Konfirmasi tindakan</h2>',
                '        <p class="kw-modal__desc">Periksa kembali sebelum melanjutkan.</p>',
                '      </div>',
                '    </div>',
                '    <button class="kw-iconbtn kw-modal__close" type="button" data-confirm-cancel aria-label="Tutup dialog"><svg aria-hidden="true"><use href="#icon-close"></use></svg></button>',
                '  </div>',
                '  <div class="kw-modal__body">',
                '    <p class="kw-confirm__message" id="kw-confirm-message"></p>',
                '  </div>',
                '  <div class="kw-modal__foot">',
                '    <button class="kw-btn kw-btn--secondary" type="button" data-confirm-cancel>Batal</button>',
                '    <button class="kw-btn kw-btn--danger" type="button" data-confirm-accept>Ya, lanjutkan</button>',
                '  </div>',
                '</div>'
            ].join("");

            var messageNode = dialog.querySelector("#kw-confirm-message");
            if (messageNode) messageNode.textContent = message;

            document.body.appendChild(dialog);
            document.body.style.overflow = "hidden";
            activeConfirm = {
                dialog: dialog,
                form: form,
                submitter: submitter,
                previousFocus: previousFocus
            };

            dialog.querySelectorAll("[data-confirm-cancel]").forEach(function (node) {
                node.addEventListener("click", function () {
                    closeConfirm(false);
                });
            });

            var accept = dialog.querySelector("[data-confirm-accept]");
            if (accept) {
                accept.addEventListener("click", function () {
                    closeConfirm(true);
                });
            }

            var cancel = dialog.querySelector(".kw-modal__foot [data-confirm-cancel]");
            if (cancel) {
                cancel.focus({ preventScroll: true });
            } else if (accept) {
                accept.focus({ preventScroll: true });
            }

            dialog.addEventListener("keydown", function (event) {
                if (event.key === "Escape") {
                    event.preventDefault();
                    closeConfirm(false);
                    return;
                }
                if (event.key !== "Tab") return;

                var items = Array.prototype.slice
                    .call(dialog.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'))
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
        }

        document.addEventListener("submit", function (event) {
            var form = event.target;
            if (!(form instanceof HTMLFormElement)) return;

            // Guard against multiple submissions while request is in progress
            if (form.dataset.kwSubmitting === "1") {
                event.preventDefault();
                return;
            }

            var confirmationSource = event.submitter ||
                form.querySelector('button[type="submit"], input[type="submit"]');
            var confirmMessage =
                (confirmationSource && confirmationSource.dataset.confirm) ||
                form.dataset.confirm;
            var alreadyConfirmed = form.dataset.kwConfirmed === "1";

            if (alreadyConfirmed) delete form.dataset.kwConfirmed;

            if (confirmMessage && !alreadyConfirmed) {
                event.preventDefault();
                openConfirm(confirmMessage, form, confirmationSource);
                return;
            }

            if (form.method.toLowerCase() !== "post" || form.dataset.loading === "off") return;

            var submitter = event.submitter || form.querySelector('button[type="submit"], input[type="submit"]');
            if (!submitter || submitter.disabled || submitter.classList.contains("is-loading")) {
                if (submitter && (submitter.disabled || submitter.classList.contains("is-loading"))) {
                    event.preventDefault();
                }
                return;
            }

            // Save original label according to element type
            if (submitter.tagName === "INPUT") {
                if (typeof submitter.dataset.originalValue === "undefined") {
                    submitter.dataset.originalValue = submitter.value;
                }
                submitter.value = "Memproses…";
            } else {
                if (typeof submitter.dataset.originalHtml === "undefined") {
                    submitter.dataset.originalHtml = submitter.innerHTML;
                }
                submitter.innerHTML = '<span class="kw-spinner" aria-hidden="true"></span><span>Memproses…</span>';
            }

            // Mark with specific dataset marker so restoreSubmitter only restores actual loading buttons
            submitter.dataset.kwLoading = "1";
            submitter.classList.add("is-loading");
            submitter.setAttribute("aria-busy", "true");
            submitter.disabled = true;
            form.dataset.kwSubmitting = "1";

            // If submitting the pipeline extraction form, display the real indeterminate progress indicator
            if (form.id === "pipeline-run-form" || form.hasAttribute("data-pipeline-form")) {
                var progressBox = document.getElementById("pipeline-progress");
                if (progressBox) {
                    progressBox.hidden = false;
                    if (typeof progressBox.scrollIntoView === "function") {
                        progressBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
                    }
                }
            }
        });

        document.querySelectorAll("[data-auto-submit]").forEach(function (control) {
            control.addEventListener("change", function () {
                if (control.form) control.form.requestSubmit();
            });
        });

        window.addEventListener("pageshow", function () {
            // Only restore elements that were explicitly placed into loading state by KataWarga
            // Never re-enable buttons that were disabled by form validation, permission, or business rules
            document.querySelectorAll('[data-kw-loading="1"], .is-loading[data-kw-loading="1"]').forEach(function (btn) {
                restoreSubmitter(btn);
            });

            document.querySelectorAll("form[data-kw-submitting]").forEach(function (form) {
                delete form.dataset.kwSubmitting;
            });

            var progressBox = document.getElementById("pipeline-progress");
            if (progressBox) progressBox.hidden = true;

            document.querySelectorAll(".kw-spinner").forEach(function (spinner) {
                var parentBtn = spinner.closest("button, a, .kw-btn");
                if (parentBtn && parentBtn.dataset.kwLoading !== "1") {
                    spinner.remove();
                }
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

    function seriesUsesIntegerValues(item) {
        return /story|cerita/i.test(String(item.unit || "")) ||
            /story|cerita/i.test(String(item.name || ""));
    }

    function formatChartValue(value, integerOnly) {
        var number = Number(value);
        if (!Number.isFinite(number)) return "0";
        if (integerOnly) return String(Math.round(number));
        var rounded = Math.round(number * 10) / 10;
        return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
    }

    function niceAxisStep(rawStep, integerOnly) {
        if (!Number.isFinite(rawStep) || rawStep <= 0) return 1;
        var magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
        var residual = rawStep / magnitude;
        var niceResidual;

        if (residual <= 1) niceResidual = 1;
        else if (residual <= 2) niceResidual = 2;
        else if (residual <= 2.5) niceResidual = 2.5;
        else if (residual <= 5) niceResidual = 5;
        else niceResidual = 10;

        var step = niceResidual * magnitude;
        if (integerOnly) step = Math.max(1, Math.round(step));
        return step;
    }

    function buildAxisTicks(maxValue, integerOnly) {
        var max = Math.max(Number(maxValue) || 0, 1);
        var step = niceAxisStep(max / 5, integerOnly);
        var top = Math.ceil(max / step) * step;
        if (top <= 0) top = step;

        var ticks = [];
        for (var value = 0; value <= top + step * 0.001; value += step) {
            ticks.push(Math.round(value * 1000) / 1000);
            if (ticks.length > 24) break;
        }
        return { ticks: ticks, top: top };
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

            var primarySeries = series[0];
            var secondarySeries = series.length > 1 ? series[1] : null;
            var primaryInteger = seriesUsesIntegerValues(primarySeries);
            var secondaryInteger = secondarySeries
                ? seriesUsesIntegerValues(secondarySeries)
                : false;

            var primaryMax = Number(primarySeries.max) || 0;
            (primarySeries.values || []).forEach(function (value) {
                primaryMax = Math.max(primaryMax, Number(value) || 0);
            });
            if (primaryMax <= 0) primaryMax = 1;

            var secondaryMax = 0;
            if (secondarySeries) {
                secondaryMax = Number(secondarySeries.max) || 0;
                (secondarySeries.values || []).forEach(function (value) {
                    secondaryMax = Math.max(secondaryMax, Number(value) || 0);
                });
                if (secondaryMax <= 0) secondaryMax = 1;
            }

            var primaryAxis = buildAxisTicks(primaryMax, primaryInteger);
            var secondaryAxis = secondarySeries
                ? buildAxisTicks(secondaryMax, secondaryInteger)
                : null;

            var renderTimer = null;
            var lastSize = "";

            function render() {
                var width = Math.max(container.clientWidth || 0, 320);
                var height = Math.max(container.clientHeight || 0, 220);
                var padding = {
                    top: 26,
                    right: secondarySeries ? 44 : 24,
                    bottom: 34,
                    left: 44
                };
                var plotWidth = width - padding.left - padding.right;
                var plotHeight = height - padding.top - padding.bottom;

                function yFor(value, top) {
                    return padding.top + plotHeight - (Number(value) / top) * plotHeight;
                }

                var svg = buildSvgElement("svg", {
                    viewBox: "0 0 " + width + " " + height,
                    role: "img",
                    "aria-label": payload.aria_label || "Grafik tren bulanan"
                });

                var title = buildSvgElement("title", {});
                title.textContent = payload.aria_label || "Grafik tren bulanan";
                svg.appendChild(title);

                if (secondarySeries) {
                    var leftTitle = buildSvgElement("text", {
                        x: padding.left,
                        y: 11,
                        "text-anchor": "start",
                        class: "kw-chart-axis-title"
                    });
                    leftTitle.textContent = "Sentimen";
                    svg.appendChild(leftTitle);

                    var rightTitle = buildSvgElement("text", {
                        x: width - padding.right,
                        y: 11,
                        "text-anchor": "end",
                        class: "kw-chart-axis-title"
                    });
                    rightTitle.textContent = "User Story";
                    svg.appendChild(rightTitle);
                }

                primaryAxis.ticks.forEach(function (tick) {
                    var y = yFor(tick, primaryAxis.top);
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
                    label.textContent = formatChartValue(tick, primaryInteger);
                    svg.appendChild(label);
                });

                if (secondaryAxis) {
                    secondaryAxis.ticks.forEach(function (tick) {
                        var y = yFor(tick, secondaryAxis.top);
                        svg.appendChild(buildSvgElement("line", {
                            x1: width - padding.right,
                            x2: width - padding.right + 4,
                            y1: y,
                            y2: y,
                            class: "kw-chart-grid"
                        }));

                        var label = buildSvgElement("text", {
                            x: width - padding.right + 8,
                            y: y + 3,
                            "text-anchor": "start",
                            class: "kw-chart-axis"
                        });
                        label.textContent = formatChartValue(tick, secondaryInteger);
                        svg.appendChild(label);
                    });
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

                var tooltip = document.createElement("div");
                tooltip.className = "kw-chart-tooltip";
                tooltip.hidden = true;

                function showTooltip(point, index) {
                    tooltip.textContent = "";

                    var heading = document.createElement("strong");
                    heading.className = "kw-chart-tooltip__title";
                    heading.textContent = String(labels[index]);
                    tooltip.appendChild(heading);

                    series.forEach(function (entry) {
                        var row = document.createElement("div");
                        row.className = "kw-chart-tooltip__row";

                        var swatch = document.createElement("span");
                        swatch.className = "kw-chart-tooltip__swatch";
                        swatch.style.background = entry.color;
                        row.appendChild(swatch);

                        var name = document.createElement("span");
                        name.textContent = String(entry.name);
                        row.appendChild(name);

                        var value = document.createElement("strong");
                        value.className = "kw-chart-tooltip__value";
                        value.textContent = formatChartValue(
                            entry.values[index],
                            seriesUsesIntegerValues(entry)
                        ) + (entry.unit ? " " + String(entry.unit) : "");
                        row.appendChild(value);

                        tooltip.appendChild(row);
                    });

                    tooltip.hidden = false;
                    var leftPercent = width ? (point.x / width) * 100 : 50;
                    tooltip.style.left = Math.min(Math.max(leftPercent, 18), 82) + "%";
                    tooltip.style.top = ((point.y / height) * 100) + "%";
                }

                function hideTooltip() {
                    tooltip.hidden = true;
                }

                series.forEach(function (item, seriesIndex) {
                    var axis = seriesIndex === 0
                        ? primaryAxis
                        : (secondaryAxis || primaryAxis);
                    var points = item.values.map(function (value, index) {
                        var x = padding.left + (labels.length > 1 ? step * index : plotWidth / 2);
                        return {
                            x: x,
                            y: yFor(Number(value) || 0, axis.top),
                            value: Number(value) || 0
                        };
                    });

                    if (points.length > 1) {
                        if (seriesIndex === 0) {
                            var areaPoints = points.map(function (point) {
                                return point.x + "," + point.y;
                            }).join(" ");
                            areaPoints += " " + points[points.length - 1].x + "," + (padding.top + plotHeight);
                            areaPoints += " " + points[0].x + "," + (padding.top + plotHeight);
                            svg.appendChild(buildSvgElement("polygon", {
                                points: areaPoints,
                                class: "kw-chart-area",
                                style: "fill:" + item.color
                            }));
                        }

                        var line = points.map(function (point) {
                            return point.x + "," + point.y;
                        }).join(" ");
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
                            "aria-label": labels[index] + ": " +
                                formatChartValue(point.value, seriesUsesIntegerValues(item)) +
                                (item.unit ? " " + String(item.unit) : "")
                        });

                        circle.addEventListener("mouseenter", function () {
                            showTooltip(point, index);
                        });
                        circle.addEventListener("mouseleave", hideTooltip);
                        circle.addEventListener("focus", function () {
                            showTooltip(point, index);
                        });
                        circle.addEventListener("blur", hideTooltip);
                        circle.addEventListener("keydown", function (event) {
                            if (event.key === "Escape") hideTooltip();
                        });
                        svg.appendChild(circle);
                    });
                });

                container.innerHTML = "";
                container.appendChild(svg);
                container.appendChild(tooltip);
            }

            function scheduleRender() {
                if (renderTimer) window.cancelAnimationFrame(renderTimer);
                renderTimer = window.requestAnimationFrame(render);
            }

            render();

            if (window.ResizeObserver) {
                var observer = new ResizeObserver(function () {
                    var nextSize = container.clientWidth + "x" + container.clientHeight;
                    if (nextSize === lastSize) return;
                    lastSize = nextSize;
                    scheduleRender();
                });
                lastSize = container.clientWidth + "x" + container.clientHeight;
                observer.observe(container);
            } else {
                window.addEventListener("resize", scheduleRender);
            }
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

        function htmxTarget(elt) {
            var selector = elt.getAttribute("hx-target");
            if (!selector) return null;
            try {
                return document.querySelector(selector);
            } catch (error) {
                return null;
            }
        }

        function restoreFromHtmxEvent(event) {
            var elt = (event.detail && event.detail.elt) || event.target;
            if (!elt) return;

            // Only restore submitters that have data-kw-loading="1" to avoid enabling non-loading buttons
            if (elt.tagName === "FORM") {
                delete elt.dataset.kwSubmitting;
                elt.querySelectorAll('[data-kw-loading="1"]').forEach(function (btn) {
                    restoreSubmitter(btn);
                });
            } else {
                restoreSubmitter(elt);
                if (elt.form) {
                    delete elt.form.dataset.kwSubmitting;
                    elt.form.querySelectorAll('[data-kw-loading="1"]').forEach(function (btn) {
                        restoreSubmitter(btn);
                    });
                }
            }

            var indicator = elt.querySelector ? elt.querySelector("[data-htmx-indicator]") : null;
            if (indicator) indicator.hidden = true;
            var target = htmxTarget(elt);
            if (target) target.setAttribute("aria-busy", "false");
        }

        document.body.addEventListener("htmx:beforeRequest", function (event) {
            var indicator = event.detail.elt.querySelector("[data-htmx-indicator]");
            if (indicator) indicator.hidden = false;
            var target = htmxTarget(event.detail.elt);
            if (target) target.setAttribute("aria-busy", "true");
        });

        document.body.addEventListener("htmx:afterRequest", restoreFromHtmxEvent);
        document.body.addEventListener("htmx:responseError", restoreFromHtmxEvent);
        document.body.addEventListener("htmx:sendError", restoreFromHtmxEvent);
        document.body.addEventListener("htmx:timeout", restoreFromHtmxEvent);
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
