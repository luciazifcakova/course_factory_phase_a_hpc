# Creating First Plots with ggplot2

**Lesson ID:** `LES-002`  
**Estimated time:** 30 minutes

Learn to generate basic visualizations using ggplot2, focusing on data mapping and essential geometric objects.

## Learning objectives

- Generate simple plots using ggplot2
- Apply data and aesthetic mappings

## Understanding ggplot2's Layered Approach

ggplot2 builds plots through layers: a base dataset, aesthetic mappings, and geometric objects. Start with `ggplot()` to initialize a plot, then add layers using functions like `geom_point()` or `geom_bar()`. This approach allows systematic customization of visual elements.

- Base plot created with `ggplot(data = <dataset>)`
- Layers added using `geom_*()` functions for different plot types

## Mapping Data to Aesthetics

Use `aes()` to define how variables in your dataset map to visual properties (aesthetics) like x/y positions, color, or size. For example, `aes(x = variable1, y = variable2)` specifies a scatter plot's axes.

- Aesthetic mappings are defined within `aes()`
- Mapped variables must exist in the dataset

## Creating Your First Plot

Combine `ggplot()` with a geometric function to generate a plot. For instance, `ggplot(data = df, aes(x = xvar, y = yvar)) + geom_point()` creates a scatter plot. Customize further with themes or labels using additional functions.

## Practical activity

### Generate a Scatter Plot

**Estimated time:** 15 minutes

1. Load the `ggplot2` package and a sample dataset (e.g., `mtcars`)
2. Create a scatter plot mapping `wt` (weight) to x-axis and `mpg` (miles per gallon) to y-axis using `geom_point()`

**Expected result:**

A scatter plot displaying the relationship between vehicle weight and fuel efficiency, with points colored by default

## Key takeaways

- ggplot2 uses a layered system for building plots
- Data-aesthetic mappings are defined with `aes()`
- Common geometric objects include `geom_point()` for scatter plots and `geom_bar()` for bar charts

## Instructor notes

- Ensure learners have completed LES-001 prerequisite material on ggplot2 fundamentals
- Remind learners to install `ggplot2` if not already done

## Sources

- `DOC-002`
