// main.js

// Landing page: "See how it works" video modal
(function () {
    var modal = document.getElementById('video-modal');
    var frame = document.getElementById('video-frame');
    var openBtn = document.querySelector('[data-video-open]');
    if (!modal || !frame || !openBtn) return;

    var closeBtn = modal.querySelector('[data-video-close]');

    function openModal() {
        var id = openBtn.getAttribute('data-video-id');
        var iframe = document.createElement('iframe');
        iframe.src = 'https://www.youtube-nocookie.com/embed/' +
            encodeURIComponent(id) + '?autoplay=1&rel=0';
        iframe.title = 'How Spendly works';
        iframe.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
        iframe.allowFullscreen = true;
        frame.appendChild(iframe);

        modal.hidden = false;
        document.body.classList.add('modal-open');
        closeBtn.focus();
    }

    function closeModal() {
        if (modal.hidden) return;
        // Removing the iframe stops playback and audio immediately.
        frame.innerHTML = '';
        modal.hidden = true;
        document.body.classList.remove('modal-open');
        openBtn.focus();
    }

    openBtn.addEventListener('click', openModal);
    closeBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', function (e) {
        if (e.target === modal) closeModal();
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeModal();
    });
})();
