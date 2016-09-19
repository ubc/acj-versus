// Holds directives used to make building forms easier
//
// Isolate this module's creation by putting it in an anonymous function
(function() {

var module = angular.module('ubc.ctlt.acj.common.form', ['ckeditor']);

/***** Directives *****/
// add the css and elements required to show bootstrap's validation feedback
// requires the parameter form-control, which passes in the input being validated
module.directive('acjFieldWithFeedback', function() {
    return {
        restrict: 'E',
        scope: {
            formControl: '='
        },
        transclude: true,
        templateUrl: 'modules/common/form-field-with-feedback-template.html'
    };
});

/* check for matching passwords; can be modified to be more general to check for the matching of any fields*/
module.directive('pwMatch', function(){
    return {
        require: 'ngModel',
        link: function (scope, elem, attrs, ctrl) {
            var firstPassword = '#' + attrs.pwMatch;
            elem.add(firstPassword).on('keyup', function () {
                scope.$apply(function () {
                    var v = elem.val()===$(firstPassword).val();
                    ctrl.$setValidity('pwMatch', v);
                });
            });
        }
    }
});

/* prompt user when leaving page with unsaved work (applied only to forms for creating answer, creating comparison) */
module.directive('confirmFormExit', function(){
    return {
        require: 'form',
        link: function(scope, elem, attrs, formController) {
            //refresh
            window.onbeforeunload = function() {
                //when confirmation is for answer AND an answer has been written or PDF file uploaded AND the user has not pressed submit
                if (attrs.formType == 'answer' && (scope.answer.content || scope.uploader.queue.length) && scope.preventExit && formController.$dirty) {
                    return "Are you sure you want to refresh this page? Any unsaved changed you've made will be lost.";
                }
                //when confirmation is for comparison AND the user has not pressed submit
                if (attrs.formType == 'compare' && scope.preventExit && formController.$dirty) {
                    return "Are you sure you want to refresh this page? Any unsaved work you've done for this round will be lost.";
                }
            }
            //change URL
            scope.$on('$locationChangeStart', function(event, next, current) {
                if (attrs.formType == 'answer' && (scope.answer.content || scope.uploader.queue.length) && scope.preventExit && formController.$dirty) {
                    if (!confirm("Are you sure you want to leave this page? Any unsaved changes you've made will be lost.")) {
                        event.preventDefault();
                    }
                }
                if (attrs.formType == 'compare' && scope.preventExit && formController.$dirty) {
                    if (!confirm("Are you sure you want to leave this page? Any unsaved work you've done for this round will be lost.")) {
                        event.preventDefault();
                    }
                }
            });
        }
    };
});

/***** Providers *****/
module.service('EditorOptions', function() {
    // For complete reference see:
    // http://docs.ckeditor.com/#!/api/CKEDITOR.config
    this.basic = {
        // do not load external custom config file
        customConfig: '',
        // The toolbar groups arrangement, optimized for two toolbar rows.
        toolbarGroups: [
            { name: 'clipboard',   groups: [ 'clipboard', 'undo' ] },
            //{ name: 'editing',     groups: [ 'find', 'selection', 'spellchecker' ] },
            { name: 'insert' },
            { name: 'links' },
            { name: 'forms' },
            //{ name: 'tools' },
            //{ name: 'document',	   groups: [ 'mode', 'document', 'doctools' ] },
            { name: 'others' },
            '/',
            { name: 'basicstyles', groups: [ 'basicstyles', 'cleanup' ] },
            { name: 'paragraph',   groups: [ 'list', 'indent', 'blocks', 'align', 'bidi' ] },
            //{ name: 'styles' },
            { name: 'colors' }
            //{ name: 'about' }
        ],
        // Remove some buttons provided by the standard plugins, which are
        // not needed in the Standard(s) toolbar.
        removeButtons: 'Cut,Copy,Paste,PasteText,PasteFromWord,Font,Anchor',

        // Set the most common block elements.
        format_tags: 'p;h1;h2;h3;pre',

        // Simplify the dialog windows.
        removeDialogTabs: 'image:advanced;link:advanced',

        // change Code Snippet's theme
        codeSnippet_theme: 'foundation',

        height: "150px",

        // enable custom plugin that combines ASCIIMath and LaTeX math input and code highlighting
        extraPlugins: 'codesnippet,combinedmath'
    };
});

// End anonymous function
})();
