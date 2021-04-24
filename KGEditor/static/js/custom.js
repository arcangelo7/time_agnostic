function get_s_p_o(jQueryButtonSelector){
    var toBeUpdated = $(jQueryButtonSelector).parent().prevAll();
    if (toBeUpdated.attr("headers") == "outgoingObject"){
        var subject = $("#resName").text();
        var predicate = toBeUpdated[1].outerText;
        var object = toBeUpdated[0].outerText;    
    } else {
        var subject = toBeUpdated[1].outerText;
        var predicate = toBeUpdated[0].outerText;
        var object = $("#resName").text();   
    }
    var triple = {
        "s": subject,
        "p": predicate,
        "o": object
    }
    return triple
}

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
            $("#sparqlQuerySubmit").html(`
                <span class="mr-1"><span class="fas fa-search"></span></span>
                Submit the query
            `);
            $("#sparqlQuerySubmit").blur();
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
                <div class="d-flex">
                    <button class="btn btn-icon-only btn-primary btn-pill ml-3 mr-3 updateButton" type="button" aria-label="update button" title="update button">
                        <span aria-hidden="true" class="fas fa-pencil-alt"></span>
                    </button>
                    <button class="btn btn-icon-only btn-primary btn-pill ml-3 mr-3 deleteButton" type="button" aria-label="delete button" title="delete button">
                        <span aria-hidden="true" class="fas fa-minus"></span>
                    </button>
                </div>
            `);
        }); 
        edit = false; 
    } else {
        edit = true; 
        $.get("/done", function(){
            res = $("#resName").text()
            window.location.href = `/entity/${res}`    
        });  
    }
});


// Click on delete button
$(document).on("click", "button.deleteButton", function(){
    triple = get_s_p_o(this)
    if ($(this).hasClass("toBeDeleted")){
        $(this).parent().prevAll().css("text-decoration", "none");
        $(this).removeClass("toBeDeleted");
        $(this).siblings().removeAttr("disabled");
        $(this).children("span").eq(0).attr("class", "fas fa-minus");
        $(this).blur();
        $.get("/undo", data={triple: triple}, function(){}, dataType="json");    
    } else {
        $(this).parent().prevAll().css("text-decoration", "line-through");
        $(this).addClass("toBeDeleted");
        $(this).siblings().prop("disabled", "true");
        $(this).children("span").eq(0).attr("class", "fas fa-plus");
        $(this).blur();
        $.get("/delete", data={triple: triple}, function(){}, dataType="json");    
    }
});

// Click on update button
$(document).on("click", "button.updateButton", function(){
    var icon = $(this).children()
    var siblingDeleteButton = $(this).siblings()
    triple = get_s_p_o(this)
    $(this).parent().prevAll().each(function(){
        if ($(this).find('.form-control').length){
            icon.attr("class", "fas fa-pencil-alt");
            siblingDeleteButton.removeAttr("disabled");
            var input = $(this).find('.form-control')
            $(this).text($(input).val());
        } else {
            icon.attr("class", "fas fa-check");
            siblingDeleteButton.prop("disabled", "true");
            var t = $(this).text();
            if (t.indexOf(' ') >= 0){
                $(this).text('').append(`
                    <div class="form-group">
                        <textarea class="form-control" rows="5">${t}</textarea>
                    </div>
                `);
            } else {
                $(this).text('').append(`
                    <div class="form-group">
                        <input type="text" class="form-control" value=${t}>
                    <div>
                `);
            }
        }
    });
    $(this).blur();
    $.get("/update", data={triple: triple}, function(){}, dataType="json");
});
