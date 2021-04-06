$( document ).ready(function() {
    $("a[href^='#d']").click(function( event ) {
        var url = window.location.href;
        var start = url.substr(url.indexOf("#"));    
        event.preventDefault();
        $(start + "p").removeClass("collapsed");
        $(`${start + "p"} + div`).removeClass("collapse");
        $('html, body').animate({
            scrollTop: $(start).offset().top
        }, 1000);
    });
});