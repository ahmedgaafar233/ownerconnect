document.addEventListener("DOMContentLoaded", function() {
    const searchInput = document.querySelector('nav#nav-filter input');
    if (!searchInput) return;

    searchInput.addEventListener('input', function(e) {
        const term = e.target.value.toLowerCase().trim();
        const sidebarItems = document.querySelectorAll('aside nav ul li');

        // First pass: Hide/Show items based on match
        sidebarItems.forEach(item => {
            if (item.classList.contains('mb-8') || item.classList.contains('mb-4')) return; // These are headers
            
            const text = item.textContent.toLowerCase();
            if (text.includes(term) || term === "") {
                item.style.setProperty('display', 'block', 'important');
            } else {
                item.style.setProperty('display', 'none', 'important');
            }
        });

        // Second pass: Hide headers if they have no visible siblings until the next header
        const headers = document.querySelectorAll('aside nav ul li.mb-8, aside nav ul li.mb-4');
        headers.forEach(header => {
            let next = header.nextElementSibling;
            let hasVisible = false;
            while (next && !next.classList.contains('mb-8') && !next.classList.contains('mb-4')) {
                if (next.style.display !== 'none') {
                    hasVisible = true;
                    break;
                }
                next = next.nextElementSibling;
            }
            header.style.setProperty('display', hasVisible || term === "" ? 'block' : 'none', 'important');
        });
    });
});
