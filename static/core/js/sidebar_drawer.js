/**
 * Sidebar Drawer — intercepts sidebar link clicks and opens
 * the target page in a slide-in panel from the right.
 */
(function () {
    "use strict";

    // Links that should navigate normally (not open in drawer)
    const NAVIGATE_LINKS = ["/admin/"];

    function shouldOpenInDrawer(href) {
        if (!href || href === "#" || href === "") return false;
        // Dashboard link should navigate normally
        if (NAVIGATE_LINKS.includes(href)) return false;
        // External links
        if (href.startsWith("http") && !href.includes(window.location.host))
            return false;
        return true;
    }

    function createDrawer() {
        // Backdrop
        const backdrop = document.createElement("div");
        backdrop.className = "drawer-backdrop";
        backdrop.addEventListener("click", closeDrawer);

        // Drawer container
        const drawer = document.createElement("div");
        drawer.className = "drawer-panel";

        // Header bar
        const header = document.createElement("div");
        header.className = "drawer-header";

        const closeBtn = document.createElement("button");
        closeBtn.className = "drawer-close";
        closeBtn.innerHTML = "✕";
        closeBtn.title = "إغلاق";
        closeBtn.addEventListener("click", closeDrawer);

        const titleEl = document.createElement("span");
        titleEl.className = "drawer-title";
        titleEl.textContent = "";

        header.appendChild(titleEl);
        header.appendChild(closeBtn);

        // Iframe
        const iframe = document.createElement("iframe");
        iframe.className = "drawer-iframe";
        iframe.setAttribute("frameborder", "0");

        // Loading spinner
        const spinner = document.createElement("div");
        spinner.className = "drawer-spinner";
        spinner.innerHTML =
            '<div class="drawer-spinner-ring"></div><span>جارِ التحميل...</span>';

        drawer.appendChild(header);
        drawer.appendChild(spinner);
        drawer.appendChild(iframe);

        document.body.appendChild(backdrop);
        document.body.appendChild(drawer);

        return { backdrop, drawer, iframe, spinner, titleEl };
    }

    let drawerEls = null;

    function openDrawer(href, title) {
        if (!drawerEls) {
            drawerEls = createDrawer();
        }

        const { backdrop, drawer, iframe, spinner, titleEl } = drawerEls;

        titleEl.textContent = title || "";
        spinner.style.display = "flex";
        iframe.style.opacity = "0";

        iframe.onload = function () {
            spinner.style.display = "none";
            iframe.style.opacity = "1";
        };

        iframe.src = href;

        // Show with animation
        requestAnimationFrame(() => {
            backdrop.classList.add("active");
            drawer.classList.add("active");
            document.body.style.overflow = "hidden";
        });
    }

    function closeDrawer() {
        if (!drawerEls) return;
        const { backdrop, drawer, iframe } = drawerEls;

        backdrop.classList.remove("active");
        drawer.classList.remove("active");
        document.body.style.overflow = "";

        // Clear iframe after animation
        setTimeout(() => {
            iframe.src = "about:blank";
        }, 300);
    }

    // Escape key closes drawer
    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") closeDrawer();
    });

    // Intercept sidebar clicks
    function attachSidebarListeners() {
        const sidebar = document.querySelector(
            'nav[class*="sidebar"], aside, [class*="navigation"], #nav-sidebar'
        );
        const container = sidebar || document;

        // Find all sidebar links
        const links = container.querySelectorAll("a[href]");
        links.forEach(function (link) {
            // Intercept sidebar links OR links with 'drawer-link' class
            const isSidebar = link.closest(
                'nav, aside, [class*="sidebar"], [class*="navigation"]'
            );
            const isManualDrawer = link.classList.contains("drawer-link");
            if (!isSidebar && !isManualDrawer) return;

            // Skip if already processed
            if (link.dataset.drawerProcessed) return;
            link.dataset.drawerProcessed = "true";

            link.addEventListener("click", function (e) {
                const href = link.getAttribute("href");
                if (!shouldOpenInDrawer(href)) return;

                e.preventDefault();
                e.stopPropagation();

                // Get only the visible title text, not Material Symbol icon names
                let title = "";
                const allSpans = link.querySelectorAll("span");
                for (const s of allSpans) {
                    if (!s.classList.contains("material-symbols-outlined")) {
                        title = s.textContent.trim();
                        if (title) break;
                    }
                }
                if (!title) {
                    // Fallback: clone the link, remove icon spans, get remaining text
                    const clone = link.cloneNode(true);
                    clone.querySelectorAll(".material-symbols-outlined").forEach(el => el.remove());
                    title = clone.textContent.trim();
                }
                openDrawer(href, title);
            });
        });
    }

    // Run after DOM is ready and after any dynamic content loads
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => {
            setTimeout(attachSidebarListeners, 500);
        });
    } else {
        setTimeout(attachSidebarListeners, 500);
    }

    // Re-attach on HTMX loads (Unfold uses HTMX)
    document.body.addEventListener("htmx:afterSettle", function () {
        setTimeout(attachSidebarListeners, 200);
    });
})();
