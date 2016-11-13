$(document).ready(function () {
    $('select').material_select();
});

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
            document.write(response.responseText);
            document.close();
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
        document.write(response.responseText);
        document.close();
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