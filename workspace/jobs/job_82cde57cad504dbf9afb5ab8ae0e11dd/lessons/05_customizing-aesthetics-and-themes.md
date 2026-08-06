# Customizing Aesthetics and Themes

**Lesson ID:** `LES-005`  
**Estimated time:** 30 minutes

Learn to modify ggplot2 themes, adjust visual elements like colors and fonts, and add annotations to improve scientific communication through clear, professional visualizations.

## Learning objectives

- Modify plot themes and annotations
- Enhance visual clarity for scientific communication

## Understanding Themes in ggplot2

Themes in ggplot2 control the non-data aspects of a plot, such as background color, grid lines, and text formatting. The default theme is 'theme_grey', but you can apply pre-defined themes like 'theme_minimal()' or 'theme_classic()' to change the overall appearance. Themes ensure consistency across visualizations and can be further customized using the theme() function.

- Themes affect layout, colors, and typography
- Pre-defined themes simplify styling
- Use theme() for granular adjustments

## Customizing Individual Aesthetic Elements

Adjust specific elements like titles, axis labels, and fonts using functions such as labs(), theme_text(), and scale_color_manual(). For example, labs() modifies axis titles and plot subtitles, while theme_text() controls font size and family. Color schemes can be tailored with scale_color_*() functions to match scientific publication standards.

- Use labs() for titles and axis labels
- theme_text() adjusts font properties
- scale_color_manual() defines custom color palettes

## Adding Annotations for Clarity

Annotations enhance plots by adding context or highlighting key findings. Use geom_text() or geom_label() to add text directly to data points, and geom_segment() to draw arrows or lines. Annotations should be concise and avoid cluttering the plot, ensuring the primary data remains the focus.

## Practical activity

### Customizing a Plot Theme and Adding Annotations

**Estimated time:** 15 minutes

1. Load the 'diamonds' dataset from ggplot2 and create a scatter plot of price vs. carat, colored by cut
2. Apply 'theme_minimal()' and adjust the plot title, axis labels, and font size using labs() and theme_text()
3. Add a text annotation highlighting the highest-priced diamond using geom_text()
4. Modify the color palette to use a scientific color scheme (e.g., 'viridis')

**Expected result:**

A scatter plot with a minimal theme, customized titles and fonts, a text annotation, and a color scheme suitable for scientific publishing

## Key takeaways

- Themes govern non-data visual elements, while aesthetics control data-related properties
- Use labs() and theme() functions to modify titles, fonts, and layout
- Annotations improve interpretability when used sparingly
- Consistent styling is critical for scientific reproducibility

## Instructor notes

- Remind learners to use theme() parameters like 'plot.title' and 'axis.title' for targeted adjustments
- Emphasize that annotations should complement, not overwhelm, the data visualization

## Sources

- `DOC-005`
