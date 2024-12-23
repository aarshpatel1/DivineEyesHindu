// display loader
$(document).ready(function () {
    // Hide the loader
    const loader = document.getElementById('loader');
    loader.style.display = 'none';

    // Show the content
    document.body.style.visibility = 'visible';
});

// top button fix js
$(window).scroll(function () {
    if (scrollY > 200) {
        $('.up-arrow').removeClass('d-none');
        $('header').addClass('sticky-top magictime slideUpReturn header-shadow');
    } else {
        $('.up-arrow').addClass('d-none');
        $('header').removeClass('sticky-top magictime slideUpReturn header-shadow');
        // Optional: Reset the animation after it's done
        setTimeout(function () {
            $('header').removeClass('slideUp');
        }, 500);
    }
});
