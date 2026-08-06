# Histograms and Other Plot Types

**Lesson ID:** `LES-004`  
**Estimated time:** 30 minutes

This lesson introduces histograms, boxplots, and other common plot types in ggplot2, focusing on their use for exploring data distributions and patterns.

## Learning objectives

- Generate histograms and boxplots
- Interpret plot outputs for data insights

## Histograms and Boxplots in ggplot2

Histograms visualize the distribution of continuous variables by dividing data into bins and counting observations per bin. Boxplots summarize distributions using quartiles, medians, and outliers. Both are essential for exploratory data analysis.

- Histograms help identify skewness, modality, and outliers in data.
- Boxplots are useful for comparing distributions across groups.

## Creating Histograms

In ggplot2, histograms are generated with `geom_histogram()`. The `x` aesthetic maps to the variable of interest, and `binwidth` controls the size of bins. The `fill` aesthetic can be used to differentiate groups.

- Use `coord_bin()` for logarithmic scaling if needed.
- Adjust `bins` or `binwidth` to optimize visualization clarity.

## Creating Boxplots

Boxplots in ggplot2 are created with `geom_boxplot()`. The `x` aesthetic typically maps to a categorical variable, while `y` maps to a continuous variable. Outliers are automatically plotted as individual points.

- Use `position_dodge()` to compare boxplots across multiple groups.
- Customize outlier visibility with `outlier.shape` and `outlier.size` parameters.

## Interpreting Plot Outputs

Effective interpretation involves identifying patterns (e.g., skewness in histograms, differences in medians in boxplots) and anomalies (e.g., extreme outliers). Always consider the context of the data and the research question.

## Practical activity

### Exploring Data Distributions

**Estimated time:** 15 minutes

1. Load a dataset (e.g., `diamonds` from ggplot2) and create a histogram for the `price` variable. Experiment with different `binwidth` values.
2. Generate a boxplot comparing `price` across different `cut` categories. Add color to differentiate groups.

**Expected result:**

Produce a histogram showing price distribution and a boxplot comparing price by cut category, with clear customization and insights about the data.

## Key takeaways

- Use `geom_histogram()` for visualizing continuous variable distributions.
- Use `geom_boxplot()` for comparing group distributions and identifying outliers.
- Customize plots to enhance clarity and align with scientific communication goals.

## Instructor notes

- Remind learners to adjust binwidth in histograms to avoid over-smoothing or under-smoothing data.
- Highlight the importance of labeling axes and adding titles for clarity in scientific contexts.

## Sources

- `DOC-004`
