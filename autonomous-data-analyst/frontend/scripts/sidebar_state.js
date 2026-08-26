try {
    window.parent.localStorage.setItem("stSidebarNav-collapsed", "false");
    window.parent.localStorage.setItem("stSidebarState", "expanded");
} catch (e) {}

function ensureSidebarExpanded() {
    try {
        const doc = window.parent.document;
        const sidebar = doc.querySelector('section[data-testid="stSidebar"]');
        if (sidebar && sidebar.getAttribute('aria-expanded') === 'false') {
            const expandBtns = doc.querySelectorAll(
                '[data-testid="stSidebarCollapsedControl"] button, ' +
                '[data-testid="stSidebarCollapseButton"] button, ' +
                '[data-testid="collapsedControl"] button, ' +
                'button[data-testid="stSidebarCollapseButton"], ' +
                'button[data-testid="stSidebarCollapsedControl"], ' +
                'button[aria-label*="sidebar" i], ' +
                'button[aria-label*="Sidebar" i]'
            );
            for (let btn of expandBtns) {
                btn.click();
            }
        }
    } catch (e) {}
}
ensureSidebarExpanded();
setTimeout(ensureSidebarExpanded, 100);
setTimeout(ensureSidebarExpanded, 400);
