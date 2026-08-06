# Scatter Plots and Bar Charts

**Lesson ID:** `LES-003`  
**Estimated time:** 30 minutes

This lesson teaches how to create scatter plots and bar charts using ggplot2, with a focus on customizing visual elements such as colors, axis labels, and titles to enhance clarity and scientific communication.

## Learning objectives

- Create scatter plots and bar charts
- Customize plot elements (e.g., colors, labels)

## Scatter Plots with ggplot2

Scatter plots are ideal for visualizing relationships between two continuous variables. In ggplot2, they are created using `geom_point()`, which maps data to visual properties (aesthetics). The x and y positions of points are determined by variables in the dataset. Customization includes adjusting point colors, sizes, and adding labels via `labs()`.

- Use `geom_point()` to create scatter plots
- Map variables to x and y aesthetics
- Customize colors with `color` or `fill` arguments

## Bar Charts with ggplot2

Bar charts display categorical data using `geom_bar()` or `geom_col()`. `geom_bar()` automatically counts observations, while `geom_col()` requires precomputed values. Bars can be customized with colors, labels, and themes to improve readability and alignment with scientific standards.

- Use `geom_bar()` for counted data or `geom_col()` for precomputed values
- Adjust bar colors with `fill` aesthetic
- Add axis labels and titles using `labs()`

## Practical activity

### Creating and Customizing Scatter Plots and Bar Charts

**Estimated time:** 15 minutes

1. Load the `ggplot2` package and explore the built-in `mtcars` dataset
2. Create a scatter plot showing the relationship between `wt` (weight) and `mpg` (miles per gallon), customizing point color and adding axis labels
3. Generate a bar chart displaying the count of cars by `cyl` (number of cylinders), adjusting bar colors and adding a title

**Expected result:**

Two plots: a scatter plot with customized aesthetics and a bar chart with labeled axes and a title

## Key takeaways

- Scatter plots use `geom_point()` to show relationships between variables
- Bar charts can be created with `geom_bar()` or `geom_col()` depending on data structure
- Customization of colors, labels, and themes improves plot clarity
- Understanding the difference between `geom_bar()` and `geom_col()` is critical for accurate visualization

## Instructor notes

- Remind learners to check data types before using `geom_bar()` (categorical vs. continuous variables)
- Highlight the importance of clear axis labels for scientific reproducibility

## Sources

- `DOC-003`
