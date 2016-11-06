$(document).ready(function () {
    $('select').material_select();
});

function disagree(theUrl) {
    $('#disagree').addClass('disabled').html('Thanks!');
    $.get(
        '/disagree',
        {url: theUrl},
        function (resp) {
            if (resp != 'ok') {
                alert('Failed to report error: ' + resp);
            }
        }
    );
}