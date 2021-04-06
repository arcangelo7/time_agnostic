$( document ).ready(function() {
    $("a[href^='#d']").click(function( event ) {
        event.preventDefault();
        var start = $(this).attr("href")
        $(start + "p").trigger("click");
        $('html, body').animate({
            scrollTop: $(start).offset().top
        }, 1000);
    });
});