\name{OPAM.apply.model.3}
\alias{OPAM.apply.model.3}
%- Also NEED an '\alias' for EACH other topic documented here.
\title{
OPAM.apply.model.3
}
\description{
%%  ~~ A concise (1-5 lines) description of what the function does. ~~
}
\usage{
OPAM.apply.model.3(input.ds, input.cls = NA, models.dir, models = "ALL", plots.outfile, cmap = NA, raw.score.outfile, norm.score.outfile, model.score.outfile, prob.outfile, gmt.file = NULL, graphics.off = F)
}
%- maybe also 'usage' for other objects documented here.
\arguments{
  \item{input.ds}{
%%     ~~Describe \code{input.ds} here~~
}
  \item{input.cls}{
%%     ~~Describe \code{input.cls} here~~
}
  \item{models.dir}{
%%     ~~Describe \code{models.dir} here~~
}
  \item{models}{
%%     ~~Describe \code{models} here~~
}
  \item{plots.outfile}{
%%     ~~Describe \code{plots.outfile} here~~
}
  \item{cmap}{
%%     ~~Describe \code{cmap} here~~
}
  \item{raw.score.outfile}{
%%     ~~Describe \code{raw.score.outfile} here~~
}
  \item{norm.score.outfile}{
%%     ~~Describe \code{norm.score.outfile} here~~
}
  \item{model.score.outfile}{
%%     ~~Describe \code{model.score.outfile} here~~
}
  \item{prob.outfile}{
%%     ~~Describe \code{prob.outfile} here~~
}
  \item{gmt.file}{
%%     ~~Describe \code{gmt.file} here~~
}
  \item{graphics.off}{
%%     ~~Describe \code{graphics.off} here~~
}
}
\details{
%%  ~~ If necessary, more details than the description above ~~
}
\value{
%%  ~Describe the value returned
%%  If it is a LIST, use
%%  \item{comp1 }{Description of 'comp1'}
%%  \item{comp2 }{Description of 'comp2'}
%% ...
}
\references{
%% ~put references to the literature/web site here ~
}
\author{
%%  ~~who you are~~
}
\note{
%%  ~~further notes~~
}

%% ~Make other sections like Warning with \section{Warning }{....} ~

\seealso{
%% ~~objects to See Also as \code{\link{help}}, ~~~
}
\examples{
##---- Should be DIRECTLY executable !! ----
##-- ==>  Define data, use random,
##--	or do  help(data=index)  for the standard data sets.

## The function is currently defined as
function (input.ds, input.cls = NA, models.dir, models = "ALL", 
    plots.outfile, cmap = NA, raw.score.outfile, norm.score.outfile, 
    model.score.outfile, prob.outfile, gmt.file = NULL, graphics.off = F) 
{
    erf <- function(x) 2 * pnorm(x * sqrt(2)) - 1
    library(gtools)
    library(verification)
    library(ROCR)
    library(MASS)
    library(RColorBrewer)
    library(MCMCpack)
    pdf(file = plots.outfile, height = 8.5, width = 11)
    dataset <- MSIG.Gct2Frame(filename = input.ds)
    m <- data.matrix(dataset$ds)
    gene.names <- dataset$row.names
    gene.descs <- dataset$descs
    sample.names <- dataset$names
    Ns <- length(m[1, ])
    Ng <- length(m[, 1])
    temp <- strsplit(input.ds, split = "/")
    s <- length(temp[[1]])
    test.file.name <- temp[[1]][s]
    temp <- strsplit(test.file.name, split = ".gct")
    test.file.prefix <- temp[[1]][1]
    if (is.na(cmap)) 
        cmap <- c(brewer.pal(n = 7, name = "Set2"), brewer.pal(n = 7, 
            name = "Dark2"), brewer.pal(n = 7, name = "Set1"))
    if (!is.na(input.cls)) {
        CLS <- MSIG.ReadClsFile(file = input.cls)
        class.labels <- CLS$class.v
        class.phen <- CLS$phen
        class.list <- CLS$class.list
    }
    else {
        class.labels <- rep(1, Ns)
        class.phen <- "UNDEFINED_PHEN"
        class.list <- rep("U", Ns)
    }
    if (models[[1]] == "ALL") {
        file.list <- list.files(models.dir)
        models <- file.list[regexpr(pattern = ".mod", file.list) > 
            1]
        for (k.model in 1:length(models)) {
            temp <- strsplit(models[k.model], ".mod")
            models[k.model] <- temp[[1]]
        }
        models <- unique(models)
    }
    n.models <- length(models)
    score.matrix <- matrix(0, nrow = n.models, ncol = Ns)
    norm.score.matrix <- matrix(0, nrow = n.models, ncol = Ns)
    model.score.matrix <- matrix(0, nrow = n.models, ncol = Ns)
    probability.matrix <- matrix(0, nrow = n.models, ncol = Ns)
    models.descs <- NULL
    for (model.i in 1:n.models) {
        print(paste(model.i, "File:", models[model.i]))
        m.file <- paste(models.dir, models[model.i], ".mod", 
            sep = "")
        con <- file(m.file, "r")
        file.content <- readLines(con, n = -1)
        close(con)
        gc()
        len <- length(file.content)
        for (i in 1:len) {
            temp <- unlist(strsplit(file.content[[i]], "\t"))
            len.param <- length(temp)
            if (len.param == 2) {
                param.vals <- temp[2]
            }
            else {
                param.vals <- paste(noquote(temp[2:len.param]), 
                  collapse = ",")
                param.vals <- paste("c(", param.vals, ")", sep = "")
            }
            assignment.string <- paste(noquote(temp[1]), " <- ", 
                param.vals, sep = "")
            eval(parse(text = assignment.string))
        }
        print(paste("Model:", model.i, " model name:", model.name))
        if (!exists("random.seed")) 
            random.seed <- 12345
        set.seed(random.seed)
        if (!exists("sample.norm.type")) 
            sample.norm.type <- "rank"
        if (sample.norm.type == "rank") {
            for (j in 1:Ns) {
                m[, j] <- rank(m[, j], ties.method = "average")
            }
            m <- 10000 * m/Ng
        }
        else if (sample.norm.type == "log.rank") {
            for (j in 1:Ns) {
                m[, j] <- rank(m[, j], ties.method = "average")
            }
            m <- log(10000 * m/Ng + exp(1))
        }
        else if (sample.norm.type == "log") {
            m[m < 1] <- 1
            m <- log(m + exp(1))
        }
        if (!exists("msig.cntrl.genes")) 
            msig.cntrl.genes <- NA
        if (!is.na(msig.cntrl.genes)) {
            gene.names.int <- intersect(msig.cntrl.genes, gene.names)
            locs <- match(gene.names.int, gene.names, nomatch = 0)
            msig.cntrl <- m[locs, ]
            msig.cntrl.genes <- gene.names[locs]
            msig.cntrl.descs <- gene.descs[locs]
            msig.cntrl.size <- length(locs)
            if (msig.cntrl.size < 1) 
                msig.cntrl.center <- rep(1, Ns)
            else if (msig.cntrl.size == 1) 
                msig.cntrl.center <- msig.cntrl
            else if (msig.cntrl.size > 1) 
                msig.cntrl.center <- apply(msig.cntrl, MARGIN = 2, 
                  FUN = mean)
            for (i in 1:Ng) {
                m[i, ] <- m[i, ]/msig.cntrl.center
            }
        }
        if (exists("msig.up.genes3")) 
            msig.up.genes <- msig.up.genes3
        gene.names.int <- intersect(msig.up.genes, gene.names)
        if (length(gene.names.int) < 2) {
            score.matrix[model.i, ] <- norm.score.matrix[model.i, 
                ] <- model.score.matrix[model.i, ] <- probability.matrix[model.i, 
                ] <- rep(0, Ns)
            models.descs <- c(models.descs, model.description)
            rm(model.creation.date, input.ds, input.cls, input2.ds, 
                input2.cls, target.class, target.class2, model.name, 
                model.description, sample.norm.type, marker.disc, 
                top.markers.up, top.markers.dn, top.markers.up2, 
                top.markers.dn2, statistic, weight, random.seed, 
                nperm, link.function, c1, msig.cntrl.genes, msig.up.genes, 
                msig.dn.genes, msig.up.genes2, msig.dn.genes2, 
                msig.up.genes3, msig.dn.genes3, beta.0, beta.1, 
                score, score.up, score.dn)
            next
        }
        if (!is.null(gmt.file)) {
            m.name <- paste(model.name, "_UP", sep = "")
            genes.string <- paste(msig.up.genes, sep = "\t", 
                collapse = "\t")
            output.line <- paste(m.name, model.description, genes.string, 
                sep = "\t", collapse = "")
            if (model.i == 1) {
                write(noquote(output.line), file = gmt.file, 
                  append = F, ncolumns = length(msig.up.genes) + 
                    2)
            }
            else {
                write(noquote(output.line), file = gmt.file, 
                  append = T, ncolumns = length(msig.up.genes) + 
                    2)
            }
            if (exists("msig.dn.genes")) {
                m.name <- paste(model.name, "_DN", sep = "")
                genes.string <- paste(msig.dn.genes, sep = "\t", 
                  collapse = "\t")
                output.line <- paste(m.name, model.description, 
                  genes.string, sep = "\t", collapse = "")
                write(noquote(output.line), file = gmt.file, 
                  append = T, ncolumns = length(msig.up.genes) + 
                    2)
            }
        }
        locs <- match(gene.names.int, gene.names, nomatch = 0)
        msig.up.test <- m[locs, ]
        msig.up.genes.test <- gene.names[locs]
        msig.up.descs.test <- gene.descs[locs]
        msig.up.size.test <- length(locs)
        if (graphics.off == F) {
            MSIG.HeatMapPlot.3(V = msig.up.test, row.names = msig.up.genes.test, 
                col.labels = class.labels, col.classes = class.phen, 
                phen.cmap = cmap, col.names = sample.names, main = paste(model.name, 
                  " UP signature test"), xlab = " ", ylab = " ", 
                sub = " ", row.norm = T, cmap.type = 4, char.rescale = 1)
        }
        OPAM <- OPAM.Projection(m, gene.names, Ns, Ng, weight, 
            statistic, msig.up.genes.test, nperm = nperm)
        score.up <- OPAM$ES.vector
        if (exists("msig.dn.genes3")) 
            msig.dn.genes <- msig.dn.genes3
        if (exists("msig.dn.genes")) {
            gene.names.int <- intersect(msig.dn.genes, gene.names)
            if (length(gene.names.int) < 2) {
                score.matrix[model.i, ] <- norm.score.matrix[model.i, 
                  ] <- model.score.matrix[model.i, ] <- probability.matrix[model.i, 
                  ] <- rep(0, Ns)
                models.descs <- c(models.descs, model.description)
                rm(model.creation.date, input.ds, input.cls, 
                  input2.ds, input2.cls, target.class, target.class2, 
                  model.name, model.description, sample.norm.type, 
                  marker.disc, top.markers.up, top.markers.dn, 
                  top.markers.up2, top.markers.dn2, statistic, 
                  weight, random.seed, nperm, link.function, 
                  c1, msig.cntrl.genes, msig.up.genes, msig.dn.genes, 
                  msig.up.genes2, msig.dn.genes2, msig.up.genes3, 
                  msig.dn.genes3, beta.0, beta.1, score, score.up, 
                  score.dn)
                next
            }
            locs <- match(gene.names.int, gene.names, nomatch = 0)
            msig.dn.test <- m[locs, ]
            msig.dn.genes.test <- gene.names[locs]
            msig.dn.descs.test <- gene.descs[locs]
            msig.dn.size.test <- length(locs)
            if (graphics.off == F) {
                MSIG.HeatMapPlot.3(V = msig.dn.test, row.names = msig.dn.genes.test, 
                  col.labels = class.labels, col.classes = class.phen, 
                  phen.cmap = cmap, col.names = sample.names, 
                  main = paste(model.name, " DN signature test"), 
                  xlab = " ", ylab = " ", sub = " ", row.norm = T, 
                  cmap.type = 4, char.rescale = 1)
            }
            OPAM <- OPAM.Projection(m, gene.names, Ns, Ng, weight, 
                statistic, msig.dn.genes.test, nperm = nperm)
            score.dn <- OPAM$ES.vector
        }
        if (!is.na(msig.cntrl.genes)) {
            if (graphics.off == F) {
                MSIG.HeatMapPlot.3(V = msig.cntrl.test, row.names = msig.cntrl.genes.test, 
                  col.labels = class.labels, col.classes = class.phen, 
                  phen.cmap = cmap, col.names = sample.names, 
                  main = paste(model.name, " CNTRL signature"), 
                  xlab = " ", ylab = " ", sub = " ", row.norm = T, 
                  cmap.type = 4, char.rescale = 1)
            }
        }
        if (exists("msig.dn.genes")) {
            score <- score.up - score.dn
        }
        else {
            score <- score.up
        }
        if (graphics.off == F) {
            if (exists("msig.dn.genes")) {
                nf <- layout(matrix(c(1, 2, 3, 0, 4, 0), 3, 2, 
                  byrow = T), widths = c(5, 1), heights = c(1, 
                  1, 1), respect = FALSE)
            }
            else {
                nf <- layout(matrix(c(1, 2), 1, 2, byrow = T), 
                  widths = c(5, 1), heights = 1, respect = FALSE)
            }
            par(mar = c(2, 4, 2, 4))
            barplot(score.up, main = paste(model.name, " OPAM Score UP (test)", 
                sep = ""), font.axis = 1.25, cex.lab = 1.5, cex.axis = 1.25, 
                cex.names = 1.25, width = 1, space = 0, col = cmap[class.labels])
            leg.txt <- class.phen
            p.vec <- rep(22, length(leg.txt))
            par(mar = c(0, 0, 0, 0))
            plot(c(0, 0), c(1, 1), xlim = c(0, 1), ylim = c(0, 
                1), axes = F, type = "n", xlab = "", ylab = "")
            legend(x = 0, y = 0.8, legend = leg.txt, bty = "n", 
                xjust = 0, yjust = 1, pch = p.vec, pt.bg = cmap, 
                col = "black", cex = 1.25, pt.cex = 2.5)
            if (exists("msig.dn.genes")) {
                par(mar = c(2, 4, 2, 4))
                barplot(score.dn, main = paste(model.name, " OPAM Score DOWN (test)", 
                  sep = ""), font.axis = 1.25, cex.lab = 1.5, 
                  cex.axis = 1.25, cex.names = 1.25, width = 1, 
                  space = 0, col = cmap[class.labels])
                par(mar = c(2, 4, 2, 4))
                barplot(score, main = paste(model.name, " OPAM Total Score (test)", 
                  sep = ""), font.axis = 1.25, cex.lab = 1.5, 
                  cex.axis = 1.25, cex.names = 1.25, width = 1, 
                  space = 0, col = cmap[class.labels])
            }
        }
        if (!exists("beta.0")) 
            beta.0 <- 0
        if (!exists("beta.1")) 
            beta.1 <- 1
        if (!exists("link.function")) 
            link.function <- "logit"
        model.formula <- "beta.0 + beta.1 * score[i]"
        model.formula
        prob.i <- matrix(0, nrow = Ns, ncol = 3)
        model.score <- vector(length = Ns, mode = "numeric")
        for (i in 1:Ns) {
            model.score[i] <- eval(parse(text = model.formula))
            if (link.function == "logit") {
                p.vec <- paste("inv.logit(x=", model.formula, 
                  ")", sep = "")
            }
            else if (link.function == "probit") {
                p.vec <- paste("(erf(", model.formula, ") + 1)/2", 
                  sep = "")
            }
            else {
                stop("Unknown link function")
            }
            val <- eval(parse(text = p.vec))
            prob.i[i, 1] <- quantile(val, probs = 0.5)
            prob.i[i, 2] <- quantile(val, probs = 0.05)
            prob.i[i, 3] <- quantile(val, probs = 0.95)
        }
        probability <- prob.i[, 1]
        xmin <- min(model.score)
        xmax <- max(model.score)
        range.x <- xmax - xmin
        n.points <- 1000
        prob.m <- matrix(0, nrow = n.points, ncol = 3)
        x.m <- vector(length = n.points, mode = "numeric")
        for (k in 1:n.points) {
            x.m[k] <- xmin + k * (range.x/n.points)
            if (link.function == "logit") {
                p.vec <- paste("inv.logit(x=", x.m[k], ")", sep = "")
            }
            else if (link.function == "probit") {
                p.vec <- paste("(erf(", x.m[k], ") + 1)/2", sep = "")
            }
            else {
                stop("Unknown link function")
            }
            val <- eval(parse(text = p.vec))
            prob.m[k, 1] <- quantile(val, probs = 0.5)
            prob.m[k, 2] <- quantile(val, probs = 0.05)
            prob.m[k, 3] <- quantile(val, probs = 0.95)
        }
        istar <- which.min(abs(0.5 - prob.m[, 1]))
        istar <- xmin + istar * (range.x/1000)
        x.index <- order(model.score, decreasing = F)
        x.order <- model.score[x.index]
        prob.i.order <- prob.i[x.index, ]
        target.var.order <- cmap[class.labels[x.index]]
        class.labels.order <- class.labels[x.index]
        boundary <- istar
        pred.class <- ifelse(prob.i.order[, 1] >= 0.5, 2, 1)
        z.range <- range(x.order)
        norm.score <- (score - min(score))/(max(score) - min(score))
        if (graphics.off == F) {
            nf <- layout(matrix(c(1, 2), 1, 2, byrow = T), widths = c(3.75, 
                1), heights = 1, respect = FALSE)
            plot(x.order, prob.i.order[, 1], sub = model.name, 
                pch = 20, col = 0, cex = 2, xlab = "Activation Index", 
                ylab = "Probability")
            points(x.m, prob.m[, 1], type = "l", lwd = 2, col = 1, 
                lty = 1, cex = 1)
            points(x.m, prob.m[, 2], type = "l", col = 4, lty = 1, 
                cex = 1)
            points(x.m, prob.m[, 3], type = "l", col = 4, lty = 1, 
                cex = 1)
            arrows(x.order, prob.i.order[, 2], x.order, prob.i.order[, 
                3], col = 4, angle = 90, code = 3, length = 0)
            range.x <- range(x.order)
            points(range.x, c(0.5, 0.5), type = "l", lty = 3, 
                col = 1, lwd = 2)
            points(range.x, c(-0.15, -0.15), type = "l", lty = 1, 
                col = 1, lwd = 2)
            points(c(istar, istar), c(-0.07, 1.07), type = "l", 
                lty = 3, col = 1, lwd = 2)
            points(x.order, prob.i.order[, 1], pch = 21, bg = target.var.order, 
                col = 1, cex = 2)
            points(x.order, rep(-0.15, length(x.order)), pch = 21, 
                bg = target.var.order, col = 1, cex = 2)
            leg.txt <- class.phen
            p.vec <- rep(22, length(leg.txt))
            c.vec <- cmap
            par(mar = c(0, 0, 0, 0))
            plot(c(0, 0), c(1, 1), xlim = c(0, 1), ylim = c(0, 
                1), axes = F, type = "n", xlab = "", ylab = "")
            legend(x = 0, y = 0.8, legend = leg.txt, bty = "n", 
                xjust = 0, yjust = 1, pch = p.vec, pt.bg = c.vec, 
                col = "black", cex = 1.25, pt.cex = 2.5)
            nf <- layout(matrix(c(1, 2, 3, 4, 5, 6), 3, 2, byrow = T), 
                widths = c(5, 1), heights = c(1, 1, 1), respect = FALSE)
            par(mar = c(4, 7, 4, 7))
            MSIG.Score.Plot(z = score, main = paste(model.name, 
                " Model Score (test)"), phen.cmap = cmap, char.rescale = 1, 
                col.classes = class.phen, col.labels = class.labels, 
                xlab = "Samples", ylab = "Score", create.window = F, 
                create.legend = T)
            par(mar = c(4, 7, 4, 7))
            MSIG.Score.Plot(z = norm.score, main = paste(model.name, 
                " Normalized Model Score (test)"), phen.cmap = cmap, 
                char.rescale = 1, col.classes = class.phen, col.labels = class.labels, 
                xlab = "Samples", ylab = "Normalized Score", 
                create.window = F, create.legend = T)
            par(mar = c(4, 7, 4, 7))
            MSIG.Score.Plot(z = prob.i[, 1], main = paste(model.name, 
                " Probabiliy (test)"), phen.cmap = cmap, char.rescale = 1, 
                col.classes = class.phen, col.labels = class.labels, 
                xlab = "Samples", ylab = "Probability", create.window = F, 
                create.legend = T)
            MSIG.HeatMapPlot.6(V = rbind(score, norm.score, model.score, 
                probability), row.names = c("raw.score", "norm.score", 
                "model.score", "probability"), row.names2 = c(model.name, 
                model.name, model.name, model.name), col.labels = class.labels, 
                col.labels2 = class.labels, col.classes = class.phen, 
                phen.cmap = cmap, phen.names = model.name, col.names = sample.names, 
                main = model.name, xlab = "  ", ylab = "  ", 
                sub = "   ", row.norm = T, cmap.type = 3, char.rescale = 1, 
                legend = T)
        }
        score.matrix[model.i, ] <- score
        norm.score.matrix[model.i, ] <- norm.score
        model.score.matrix[model.i, ] <- model.score
        probability.matrix[model.i, ] <- probability
        models.descs <- c(models.descs, model.description)
        rm(model.creation.date, input.ds, input.cls, input2.ds, 
            input2.cls, target.class, target.class2, model.name, 
            model.description, sample.norm.type, marker.disc, 
            top.markers.up, top.markers.dn, top.markers.up2, 
            top.markers.dn2, statistic, weight, random.seed, 
            nperm, link.function, c1, msig.cntrl.genes, msig.up.genes, 
            msig.dn.genes, msig.up.genes2, msig.dn.genes2, msig.up.genes3, 
            msig.dn.genes3, beta.0, beta.1, score, score.up, 
            score.dn)
        if (graphics.off == F) {
            if (model.i\%\%5 == 0) {
                graphics.off()
                gc()
            }
        }
    }
    MSIG.HeatMapPlot.6(V = score.matrix, row.names = models, 
        row.names2 = models.descs, col.labels = class.labels, 
        col.labels2 = class.labels, col.classes = class.phen, 
        phen.cmap = cmap, col.names = sample.names, main = paste(test.file.name, 
            " - Raw Scores"), xlab = " ", ylab = " ", sub = "Raw Scores", 
        row.norm = T, cmap.type = 3, char.rescale = 1, legend = T)
    MSIG.HeatMapPlot.6(V = norm.score.matrix, row.names = models, 
        row.names2 = models.descs, col.labels = class.labels, 
        col.labels2 = class.labels, col.classes = class.phen, 
        phen.cmap = cmap, col.names = sample.names, main = paste(test.file.name, 
            " - Norm Scores"), xlab = " ", ylab = " ", sub = "Norm Scores", 
        row.norm = T, cmap.type = 3, char.rescale = 1, legend = T)
    MSIG.HeatMapPlot.6(V = model.score.matrix, row.names = models, 
        row.names2 = models.descs, col.labels = class.labels, 
        col.labels2 = class.labels, col.classes = class.phen, 
        phen.cmap = cmap, col.names = sample.names, main = paste(test.file.name, 
            " - Model Scores"), xlab = " ", ylab = " ", sub = "Model Scores", 
        row.norm = T, cmap.type = 3, char.rescale = 1, legend = T)
    MSIG.HeatMapPlot.6(V = probability.matrix, row.names = models, 
        row.names2 = models.descs, col.labels = class.labels, 
        col.labels2 = class.labels, col.classes = class.phen, 
        phen.cmap = cmap, col.names = sample.names, main = paste(test.file.name, 
            " - Probabilities"), xlab = " ", ylab = " ", sub = "Probabilities", 
        row.norm = T, cmap.type = 3, char.rescale = 1, legend = T)
    V.GCT <- data.frame(score.matrix)
    names(V.GCT) <- sample.names
    row.names(V.GCT) <- models
    write.gct(gct.data.frame = V.GCT, descs = models.descs, filename = raw.score.outfile)
    V.GCT <- data.frame(norm.score.matrix)
    names(V.GCT) <- sample.names
    row.names(V.GCT) <- models
    write.gct(gct.data.frame = V.GCT, descs = models.descs, filename = norm.score.outfile)
    V.GCT <- data.frame(model.score.matrix)
    names(V.GCT) <- sample.names
    row.names(V.GCT) <- models
    write.gct(gct.data.frame = V.GCT, descs = models.descs, filename = model.score.outfile)
    V.GCT <- data.frame(probability.matrix)
    names(V.GCT) <- sample.names
    row.names(V.GCT) <- models
    write.gct(gct.data.frame = V.GCT, descs = models.descs, filename = prob.outfile)
    dev.off()
  }
}
% Add one or more standard keywords, see file 'KEYWORDS' in the
% R documentation directory.
\keyword{ ~kwd1 }
\keyword{ ~kwd2 }% __ONLY ONE__ keyword per line
