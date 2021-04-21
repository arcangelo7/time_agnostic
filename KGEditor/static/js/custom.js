// Click on sumbit query
$("#sparqlQuerySubmit").on("click", function(){
    var query = $("textarea#sparqlEndpoint").val()
    $("#sparqlQuerySubmit").html(`
        <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
        <span class="ml-1">Loading...</span>
    `);
    $.get("/sparql", data={"query": query}, function(data){
        $("#sparqlResults thead tr").empty();
        $("#sparqlResults tbody").empty();
        $("#alert").empty();
        if (data["results"] == "error"){
            $("#alert").html(`
                <div class="alert alert-danger alert-dismissible shadow-soft fade show" role="alert">
                    <span class="alert-inner--icon"><span class="fas fa-exclamation-circle"></span></span>
                    <span class="alert-inner--text"><strong>Oh snap!</strong> Change a few things up and try
                        submitting again.</span>
                    <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                        <span aria-hidden="true">&times;</span>
                    </button>
                </div>                
            `)
            return
        }
        var vars = data["head"]["vars"];
        $.each(vars, function(index, value){
            $("#sparqlResults thead tr").append(`
                <th class="border-0" scope="col" id="sparqlVar-${value}">${value}</th>
            `);
        });
        var results = data["results"]["bindings"];
        $.each(results, function(i, result){
            $("#sparqlResults tbody").append(`<tr id="sparqlResults${i}"></tr>`)
            $.each(vars, function(j, variable){
                var res = result[variable]["value"]
                if (res.includes(baseUri) && variable != "p"){
                    $(`tr#sparqlResults${i}`).append(`
                        <td headers="sparqlVar-${variable}">
                            <a href="#" class="sparqlEntity">
                                ${res}
                            </a>
                        </td>
                    `)
                } else {
                    $(`tr#sparqlResults${i}`).append(`
                        <td headers="sparqlVar-${variable}">
                            ${res}
                        </td>
                    `)                    
                }
            });
        });
        $("#sparqlQuerySubmit").html(`
            <span class="mr-1"><span class="fas fa-search"></span></span>
            Submit the query
        `);
        $("#sparqlQuerySubmit").blur();
    });
});

// Click on entity
$(document).on("click", "a.sparqlEntity", function(e){
    e.preventDefault();
    var res = encodeURI($.trim($(this).text()));
    window.location.href = "/entity/" + res;
});

// Click on edit button
var edit = true;
$("#editButton").click(function(){
    if (edit){
        $(this)
            .html(`
                <span class="mr-1"><span class="fas fa-check"></span></span>
                Done
            `)
            .removeClass("btn-success")
            .addClass("btn-danger")
            .blur();
        $("tbody tr").each(function(){
            $(this).append(`
                <button class="btn btn-icon-only btn-primary btn-pill ml-3 mr-3 deleteButton" type="button" aria-label="love button" title="love button">
                    <span aria-hidden="true" class="fas fa-minus"></span>
                </button>
            `);
        }); 
        edit = false; 
    } else {
        edit = true; 
        $.get("/done", function(){
            res = $("#resName").text()
            window.location.href = `/entity/${res}`    
        });
        // $(this)
        //     .html(`
        //         <span class="mr-1"><span class="fas fa-pen-fancy"></span></span>
        //         Edit
        //     `)
        //     .removeClass("btn-danger")
        //     .addClass("btn-success")
        //     .blur();
        // $(".deleteButton").remove();   
    }

});

// Click on delete button
$(document).on("click", "button.deleteButton", function(){
    var toBeDeleted = $(this).prevAll();
    if (toBeDeleted.attr("headers") == "outgoingObject"){
        var subject = $("#resName").text();
        var predicate = toBeDeleted[1].outerText;
        var object = toBeDeleted[0].outerText;    
    } else {
        var subject = toBeDeleted[1].outerText;
        var predicate = toBeDeleted[0].outerText;
        var object = $("#resName").text();   
    }
    var triple = {
        "s": subject,
        "p": predicate,
        "o": object
    }
    $.get("/delete", data={triple: triple}, function(){}, dataType="json");
});
