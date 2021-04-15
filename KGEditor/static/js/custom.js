$("#sparqlQuerySubmit").on("click", function(){
    var query = $("textarea#sparqlEndpoint").val()
    $.get("/sparql", data={"query": query}, function(data){
        $("#sparqlResults thead tr").empty();
        $("#sparqlResults tbody").empty();
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
                    <td headers="sparqlVar-${variable}">
                        <a href="#" class="sparqlEntity">
                            ${res}
                        </a>
                    </td>
                `);
            });
        });
    });
});

$(document).on("click", "a.sparqlEntity", function(e){
    e.preventDefault();
    var res = encodeURI($.trim($(this).text()));
    console.log(res)
    window.location.href = '/entity/' + res
});
