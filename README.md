# Fast Deep Zoom Pyramid Generator

# Introduction

Deep Zoom images consist of a set of tiles created from a large original image.
This set of tiles is also often called a pyramid.

There are many formats and viewers, each one with small differences in the image layout format.
This particular generator conforms to the DZI ( Microsoft Deep Zoom format ).
To learn more visit the [OpenZoom project homepage](http://www.openzoom.org/).

Normal Pyramid generators take one large image as input and produce the tiles and necessary folder structure.
This approach is pretty simple to understand and use.
However, we needed to radically improve performance and memory consumption and that forced us to look for an alternative strategy.

## Tweak 1: Pre-Tiling

Instead of starting from the complete original image,
this generator expects a set of tiles at the highest resolution level.
This is equivalent to taking the original source image you would pass in 
to a normal generator and creating unscaled first level of tiles by hand.

## Tweak 2: Patches

If you make a change to the image and you need to regenerate the pyramid 
you will only need to update the modified tile(s) and its ancestors will be re-generated.

## Tweak 3: No Overlap

While in some browsers a tile `overlap = 0` yields some visual artifacts,
eliminating the overlap allows us to reduce the generation processing load 
by about a factor of four, as well as make the algorithm brain-dead simple.

Using `overlap >= 1` will be explored soon.
It wont' change the user API and folder conventions,
just make the generator a bit more complex.

## Tweak 4: OpenCV

# Usage Overview

Imagine you have an image called image1.jpg that measures `750 x 500 pixels`.
We want to create a Deep Zoom pyramid with a tile size of 250px.

In a regular pyramid generator you would just pass the image and the tile dimension as input.
In this case, we need to provide the base tiles by hand
( while it seems like more work now, the benefits will soon become obvious ).

## Provide base tiles by hand

We would need to create 6 tiles, and each will measure exactly 250px.

    image1/
      pyramid.json
      v0/
        0_0.jpg
        0_1.jpg
        0_2.jpg
        1_0.jpg
        1_1.jpg
        1_2.jpg

The file `pyramid.json` contains information about the image:

    {
        width: 750,
        height: 500,
        tile_size: 250,
        overlap: 0
    }

Some of these parameters could have been resolved by looking at the src images directly, but we prefer to have them explicitly defined in order to provide an extra consistency check.
IMPORTANT: For now, `overlap=0` is the only possible value ( the incremental generator is assuming this to simplify calculations ).

We run the script in order to generate the first version of this pyramid.

    $ fast_pyramid ./image1

As a result of running this process, more folders are created inside the image1 folder, and it ends up looking something like this:

    image1/
      v0/...
      dest/
        dzi/
          v0/
            dzi.xml
            dzi_files/
              0/...
              1/...
              ...
              10/
                0_0.jpg ( --> link to ../../../../v0/0_0.jpg )
                0_1.jpg ( --> link to ../../../../v0/0_1.jpg )
                ...

Notice that, since the original .jpg tiles located in the src/v0 folder are "ready to be served", we just link to them.
In general, we use links wherever we can to make things more efficient ( space + speed )

We’re done with our first generation process: `/image1/dzi/dzi.xml` is a valid DZI image URL ;) which can be served via HTTP.

Now. Imagine that a small part of the image changes and we want to generate a new version.
We only need to place the 'changed' tiles in the `/src/v{next_version}` folder:

    image1/
      pyramid.json
      v0/...
      v1/
        0_0.jpg

Let’s generate the pyramid, once again:

    $ fast_pyramid ./image1

Which will yield the expected result, using links to previously generated images whenever possible

    image1/
      pyramid.json
      v0/... 
      v1/...
      dest/
        dzi/
          v0/...
          v1/
            dzi.xml
            dzi_files/
              0/...
              1/...
              ...
              10/
                0_0.jpg ( --> link to ../../../../src/v1/0_0.jpg )
                0_1.jpg ( --> link to ../../../../src/v0/0_1.jpg )

# Random Notes

* All the *source* data is located in the `./v{x}/` folders. Thus, you can delete the `./dest/` folder at any time and regenerate from here.
* Generating a version will ensure that all previous versions are present.
* The first generation (v0) is usually the longest because it will need to generate the complete pyramid. Subsequent generations only generate the delta

# Vacuum

Not implemented yet. But we should provide a way of eliminating a range of intermediate versions to save up space. We will see if we need this once we have some numbers to perform calculations.

# Efficiently serving over the web

* When serving the images via HTTP, a smart browser could be devised that understands links and generates 303 or 304 HTTP headers.
This can help to reduce traffic, specially when dealing with a CDN or some other HTTP-Caching-heavy architecture.

# Benchmarks






# Etc


http://www.vips.ecs.soton.ac.uk/index.php?title=Libvips
http://www.vips.ecs.soton.ac.uk/index.php?title=Speed_and_Memory_Use
http://stackoverflow.com/questions/3681496/opencv-macport-python-bindings


