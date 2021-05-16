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

function transformEntitiesInLinks(){
    $(".tripleMember").each(function(){
        var tripleMember = $(this).html();
        predicatesWithLiteralObjects = ["https://w3id.org/oc/ontology/hasUpdateQuery", "http://purl.org/dc/terms/description"]
        if (tripleMember.indexOf(baseUri) != -1 && !predicatesWithLiteralObjects.includes($(this).siblings("td[headers='outgoingPredicate']").text())){
            $(this).wrapInner(`<a href='' class='sparqlEntity'></a>`)
        }
    });
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
                $(`tr#sparqlResults${i}`).append(`
                    <td headers="sparqlVar-${variable}" class='tripleMember'>
                        ${res}
                    </td>
                `)                    
            });
        });
        $("#sparqlQuerySubmit").html(`
            <span class="mr-1"><span class="fas fa-search"></span></span>
            Submit the query
        `);
        $("#sparqlQuerySubmit").blur();
        transformEntitiesInLinks();
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
        $.get("/getRA", function(data){
            if (data["result"] == ""){
                $("#modalResponsibleAgent").modal("show");
            } else {
                $("#submitResponsibleAgent").trigger("click");
            }
        });
    } else {
        edit = true; 
        $.get("/done", function(){
            res = $("#resName").text()
            window.location.href = `/entity/${res}`    
        });  
    }
});

$(document).on("click", "#submitResponsibleAgent", function(){ 
    let orcid_re = /(https?:\/\/orcid.org\/)?([0-9]{4})-([0-9]{4})-([0-9]{4})-([0-9]{4})/i
    $.get("/getRA", function(data){
        if (data["result"] == ""){
            resp_agent = $("#inputResponsibleAgent").val();
            is_an_orcid = orcid_re.exec(resp_agent)
            if (is_an_orcid){
                $.get("/saveRA", data={resp_agent: resp_agent}, function(){}, dataType="json");
                $("#modalResponsibleAgent").modal("hide");    
            } else {
                $("#invalidOrcid").removeAttr("hidden");
                $("#submitResponsibleAgent").blur();
            }
        } else {
            resp_agent = data["result"];
            is_an_orcid = true;
        }
        if (edit && is_an_orcid){
            $("#editButton")
                .html(`
                    <span class="mr-1"><span class="fas fa-check"></span></span>
                    Done
                `)
                .removeClass("btn-success")
                .addClass("btn-danger")
                .blur();
            $("#resName").append(`
                <button class="btn btn-icon-only btn-primary btn-pill ml-3 mr-3 createButton" type="button" aria-label="create button" title="create button" data-toggle="modal" data-target="#modalCreateEntity">
                    <span aria-hidden="true" class="fas fa-plus"></span>
                </button>
            `);
            $("tbody tr").each(function(){
                if ($(this).text().indexOf("/prov") == -1 && $("#resName").text().indexOf("/prov") == -1){
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
                }
            }); 
            edit = false; 
        }     
    });
});

$('#modalResponsibleAgent').on('hidden.bs.modal', function (e) {
    $("#invalidOrcid").prop("hidden", "true");
});

// Click on create button 
$(document).on("click", "button#submitCreate", function(){
    $('#modalCreateEntity').modal('hide')
    subject = $("#createSubject").val();
    predicate = $("#createPredicate").val();
    object = $("#createObject").val();
    var triple = {
        "s": subject,
        "p": predicate,
        "o": object
    }
    $.get("/create", data={triple: triple}, function(){}, dataType="json");
});

// Click on update button
var prev_triple;
$(document).on("click", "button.updateButton", function(){
    var button = this
    var icon = $(this).children()
    var siblingDeleteButton = $(this).siblings()
    if (!$(this).parent().prevAll().find(".form-control").length) {
        prev_triple = get_s_p_o(button);
    } 
    $(this).parent().prevAll().each(function(){
        if ($(this).find('.form-control').length){
            icon.attr("class", "fas fa-pencil-alt");
            siblingDeleteButton.removeAttr("disabled");
            var input = $(this).find('.form-control')
            var t = $(input).val()
            if (t.indexOf(baseUri) >= 0){
                $(this).html(`<a href="" class="sparqlEntity">${t}</a>`)
            } else {
                $(this).text(t);
            }
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
    if (!$(this).parent().prevAll().find(".form-control").length) {
        new_triple = get_s_p_o(button);
        $.get("/update", data={prev_triple: prev_triple, new_triple: new_triple}, function(){}, dataType="json");
    } 
    $(this).blur();
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

$(function() {
    // Create triple autocompletion
    $.getJSON("/static/config/config.json", function(){
    })
    .done(function(data) {
        var createPredicate = []
        $.each(data, function(k, v){
            $.each(v, function(k, v){
                createPredicate.push(k)
            });
        });
        $("#createPredicate").autocomplete({
            source: createPredicate
        });
    })
    .fail(function(e) {
        console.log(e);
    });

    transformEntitiesInLinks();
});
