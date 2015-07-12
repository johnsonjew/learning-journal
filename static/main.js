$(function() {
    $(".hide-on-start").hide();
    $("#edit_button").on("click", function (event) {
        event.preventDefault();
        $("#jtitle").toggle();
        $("#menu").toggle();
        $("#jsform").toggle();
        $(".entry").toggle();
    });
    $("form#jsform").on("submit", function (event) {
        event.preventDefault();
        var title = $("#title").val();
        var text = $("#text").val();
        var pathArray = window.location.pathname.split( '/' );
        $.ajax ({
            method: "POST",
            url: "/edit_post/" + pathArray[2],
            data: {
                title: title,
                text: text
            }
        }).done(function(data) {
            $(".title").html(data.title)
            $(".entry_body").html(data.text)
            $("#jtitle").toggle();
            $("#menu").toggle();
            $("#jsform").toggle();
            $(".entry").toggle();
            console.log(data);
        }).error(function(error){
            console.log(error)
        });
    })
})
