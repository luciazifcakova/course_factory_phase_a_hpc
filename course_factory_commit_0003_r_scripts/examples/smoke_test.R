dir.create("figures", showWarnings = FALSE)
png("figures/smoke.png", width = 800, height = 500)
plot(iris$Sepal.Length, iris$Sepal.Width)
dev.off()

write.csv(
  head(iris),
  "iris_head.csv",
  row.names = FALSE
)

cat("Course Factory R smoke test completed.\n")
