var gulp = require('gulp'),
    gulpIgnore = require('gulp-ignore'),
    minifyHTML = require('gulp-minify-html'),
    // templateCache = require('gulp-angular-templatecache'),
    jshint = require('gulp-jshint'),
    gzip = require('gulp-gzip'),
    uglify = require('gulp-uglify'),
    concat = require('gulp-concat'),
    sourcemaps = require('gulp-sourcemaps'),
    ngAnnotate = require('gulp-ng-annotate');


// paths relative to the project root
var staticfiles_root = 'fabricdemo/staticfiles/',
    paths = {
        root: {
            root: staticfiles_root,
            src: {
                root: staticfiles_root + 'src/',
                js: staticfiles_root + 'src/js/',
                css: staticfiles_root + 'src/css',
                fonts: staticfiles_root + 'src/fonts/',
                images: staticfiles_root + 'src/images/'
            },
            dist: {
                root: staticfiles_root + 'dist/',
                js: staticfiles_root + 'dist/js/',
                css: staticfiles_root + 'dist/css',
                fonts: staticfiles_root + 'dist/fonts/',
                images: staticfiles_root + 'dist/images/'
            }
        },
        bower: 'bower_components/',
        node: 'node_modules/'
    };


gulp.task('build:libs', function () {
    // bundle any 3rd parth libraries
    var libs = [
        paths.bower + 'angular/angular.js',
        paths.bower + 'angular-animate/angular-animate.js',
        paths.bower + 'angular-ui-router/release/angular-ui-router.js',
        paths.bower + 'momentjs/moment.js',
        paths.bower + 'underscore/underscore.js'
    ];

    return gulp.src(libs)
        .pipe(sourcemaps.init({loadMaps: true}))
        .pipe(concat('libs.js'))
        .pipe(uglify())
        .pipe(sourcemaps.write('.'))
        .pipe(gulp.dest(paths.root.dist.js));
});


gulp.task('build:gzip', ['build:libs'], function () {
    return gulp.src(paths.root.dist.js + '/*.js')
        .pipe(gzip())
        .pipe(gulp.dest(paths.root.dist.js));
});


gulp.task('build:app', function () {
    return gulp.src([
            paths.root.src.js + '/*.js',
            '!' + paths.root.src.js + '**/tests/**',
        ])
        .pipe(sourcemaps.init({loadMaps: true})
        .pipe(concat('app.js'))
        .pipe(uglify())
        .pipe(sourcemaps.write('.'))
        .pipe(gulp.dest(paths.root.dist.js));
});


gulp.task('default', ['build:gzip', 'build:app']);
