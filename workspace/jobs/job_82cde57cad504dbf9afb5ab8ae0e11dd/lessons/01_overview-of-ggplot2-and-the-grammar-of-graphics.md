# Overview of ggplot2 and the Grammar of Graphics

**Lesson ID:** `LES-001`  
**Estimated time:** 30 minutes

Introduces the foundational principles of ggplot2, emphasizing its layered architecture and the Grammar of Graphics framework for creating visualizations.

## Learning objectives

- Understand the layered approach of ggplot2
- Learn the core components of the grammar of graphics

## The Grammar of Graphics

The Grammar of Graphics is a systematic approach to building visualizations by combining data, visual properties (aesthetics), and geometric objects (geoms). This framework forms the basis of ggplot2, allowing users to construct plots through a series of logical layers.

- Data: The dataset used for visualization
- Aesthetics: Mapping data variables to visual properties (e.g., x/y position, color, size)
- Geoms: The visual elements representing data (e.g., points, bars, lines)

## Layered Approach in ggplot2

ggplot2 builds plots incrementally by adding layers that define different aspects of the visualization. Each layer can modify the plot's appearance or add new information, such as background grids, annotations, or statistical transformations.

- Base layer: Initialize the plot with `ggplot()` and specify the dataset
- Aesthetic layer: Define variable-to-visual-property mappings with `aes()`
- Geom layer: Add geometric objects using functions like `geom_point()` or `geom_bar()`

## Practical activity

### Create a Basic Scatter Plot

**Estimated time:** 15 minutes

1. Load the `ggplot2` package and access the built-in `mtcars` dataset
2. Use `ggplot()` to initialize the plot, mapping `wt` (weight) to x-axis and `mpg` (miles per gallon) to y-axis with `aes()`
3. Add a geom layer using `geom_point()` to create the scatter plot

**Expected result:**

A scatter plot displaying the relationship between vehicle weight and fuel efficiency, with points representing individual cars

## Key takeaways

- ggplot2 uses the Grammar of Graphics to create visualizations through layered components
- Plots are constructed by combining data, aesthetics, and geometric objects
- Customization is achieved by adding or modifying layers incrementally

## Instructor notes

- Ensure learners understand that `ggplot2` requires explicit specification of all plot components
- Remind learners to check for dataset availability if using `mtcars` (it is included in `ggplot2`)

## Sources

- `DOC-001`
