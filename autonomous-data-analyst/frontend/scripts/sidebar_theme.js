(function() {

    var LIGHT_BACKGROUNDS = [
        'rgb(255, 255, 255)',
        'rgb(254, 254, 254)',
        'rgb(250, 250, 250)',
        'rgb(248, 249, 250)',
        'rgb(245, 245, 245)',
        'rgb(243, 244, 246)',
        'rgb(240, 242, 246)',
        'rgb(238, 238, 238)',
        'rgb(230, 230, 230)',
        'rgb(249, 250, 251)',
        'rgb(247, 247, 247)',
    ];

    function isLightBg(bg) {
        if (!bg || bg === 'transparent' || bg === 'rgba(0, 0, 0, 0)') return false;
        return LIGHT_BACKGROUNDS.indexOf(bg) !== -1;
    }

    function patchSidebarWhiteBoxes() {
        try {
            var doc = window.parent.document;
            var sidebar = doc.querySelector('[data-testid="stSidebar"]');
            if (!sidebar) return;

            var allEls = sidebar.querySelectorAll('*');
            allEls.forEach(function(el) {
                try {
                    var computedBg = window.getComputedStyle(el).backgroundColor;
                    if (isLightBg(computedBg)) {
                        el.style.setProperty('background-color', '#1e293b', 'important');
                        el.style.setProperty('background', '#1e293b', 'important');

                        var newBg = window.getComputedStyle(el).backgroundColor;
                        if (isLightBg(newBg)) {
                            el.style.setProperty('color', '#0f172a', 'important');
                            el.querySelectorAll('*').forEach(function(child) {
                                child.style.setProperty('color', '#0f172a', 'important');
                            });
                        } else {
                            el.style.setProperty('color', '#f1f5f9', 'important');
                        }
                    }
                } catch(e2) {}
            });

        } catch(e) {}
    }

    patchSidebarWhiteBoxes();
    setTimeout(patchSidebarWhiteBoxes, 200);
    setTimeout(patchSidebarWhiteBoxes, 600);
    setTimeout(patchSidebarWhiteBoxes, 1500);
    setTimeout(patchSidebarWhiteBoxes, 3500);

    try {
        var obs = new MutationObserver(function(mutations) {
            for (var i = 0; i < mutations.length; i++) {
                if (mutations[i].addedNodes.length > 0) {
                    setTimeout(patchSidebarWhiteBoxes, 50);
                    break;
                }
            }
        });
        obs.observe(window.parent.document.body, { childList: true, subtree: true });
    } catch(e) {}

})();
