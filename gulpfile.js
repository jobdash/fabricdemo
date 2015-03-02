var gulp = require('gulp'),
    gulpIgnore = require('gulp-ignore'),
    minifyHTML = require('gulp-minify-html'),
    templateCache = require('gulp-angular-templatecache'),
    jshint = require('gulp-jshint'),
    uglify = require('gulp-uglify'),
    concat = require('gulp-concat'),
    ngAnnotate = require('gulp-ng-annotate');

var staticfiles_root = 'fabricdemo/staticfiles/',
    paths = {
        root: {
            root: staticfiles_root,
            js: staticfiles_root + 'js/',
            css: staticfiles_root + 'css/',
            fonts: staticfiles_root + 'fonts/',
            images: staticfiles_root + 'images/'
        }
    }
