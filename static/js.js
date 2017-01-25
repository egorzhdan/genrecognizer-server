$(document).ready(function () {
    $('select').material_select();
});

function handleError(response) {
    if (response.responseText) {
        alert(response.responseText);
    } else {
        alert("Got empty response from the server");
    }
}

function localSubmit() {
    $('#main').hide();
    $('#loader').show();

    var ddata = new FormData(document.querySelector('#local-form'));
    $.ajax({
        url: 'recognize',
        type: 'POST',
        data: ddata,
        success: function (data) {
            $('#main-div').html(data);
        },
        error: function (response, text, error) {
            handleError(response);
        },
        cache: false,
        contentType: false,
        processData: false
    });
}

function webSubmit() {
    $('#main').hide();
    $('#loader').show();
    $.post('recognize', $('#web-form').serialize(), function (data) {
        $('#main-div').html(data);
    }).fail(function (response) {
        handleError(response);
    });
}

function agree(theUrl, theTitle, thePredicted) {
    $('#agree').addClass('disabled').html('Thanks!');
    $.get(
        '/agree',
        {url: theUrl, title: theTitle, predicted: thePredicted},
        function (resp) {
            if (resp != 'ok') {
                alert('Failed to report: ' + resp);
            }
        }
    );
}

function disagree(theUrl, theTitle, thePredicted) {
    $('#disagree').addClass('disabled').html('Thanks!');
    $.get(
        '/disagree',
        {url: theUrl, title: theTitle, predicted: thePredicted},
        function (resp) {
            if (resp != 'ok') {
                alert('Failed to report: ' + resp);
            }
        }
    );
}