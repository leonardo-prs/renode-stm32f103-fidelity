<!-- page 1 -->

# Computer Architecture Formulas

1. $CPU\ time = Instruction\ count \times Clock\ cycles\ per\ instruction \times Clock\ cycle\ time$
2. $X\ is\ n\ times\ faster\ than\ Y:\ n = \frac{Execution\ time_Y}{Execution\ time_X} = \frac{Performance_X}{Performance_Y}$
3. Amdahl's Law: $\text{Speedup}_{\text{overall}} = \frac{Execution\ time_{\text{old}}}{Execution\ time_{\text{new}}} = \frac{1}{(1 - \text{Fraction}_{\text{enhanced}}) + \frac{\text{Fraction}_{\text{enhanced}}}{\text{Speedup}_{\text{enhanced}}}}$
4. $Energy_{\text{dynamic}} \propto \frac{1}{2} \times \text{Capacitive\ load} \times \text{Voltage}^2$
5. $Power_{\text{dynamic}} \propto \frac{1}{2} \times \text{Capacitive\ load} \times \text{Voltage}^2 \times \text{Frequency\ switched}$
6. $Power_{\text{static}} \propto Current_{\text{static}} \times Voltage$
7. $Availability = \frac{\text{Mean time to fail}}{(\text{Mean time to fail} + \text{Mean time to repair})}$
8. $\text{Die\ yield} = \text{Wafer\ yield} \times \frac{1}{(1 + \text{Defects\ per\ unit\ area} \times \text{Die\ area})^N}$

where Wafer yield accounts for wafers that are so bad they need not be tested and $N$ is a parameter called the process-complexity factor, a measure of manufacturing difficulty. $N$ ranges from $11.5$ to $15.5$ in $2011$.

9. Means—arithmetic ($AM$), weighted arithmetic ($WAM$), and geometric ($GM$):
$$\text{AM} = \frac{1}{n} \sum_{i=1}^{n} \text{Time}_i, \quad \text{WAM} = \sum_{i=1}^{n} \text{Weight}_i \times \text{Time}_i, \quad \text{GM} = \sqrt[n]{\prod_{i=1}^{n} \text{Time}_i}$$

where $\text{Time}_i$ is the execution time for the $i$th program of a total of $n$ in the workload, $\text{Weight}_i$, is the weighting of the $i$th program in the workload.

10. Average memory-access time = Hit time + Miss rate $\times$ Miss penalty
11. Misses per instruction = Miss rate $\times$ Memory access per instruction
12. Cache index size: $2^{\text{index}} = \frac{\text{Cache\ size}}{(\text{Block\ size} \times \text{Set\ associativity})}$
13. Power Utilization Effectiveness ($PUE$) of a Warehouse Scale Computer $= \frac{\text{Total Facility Power}}{\text{IT Equipment Power}}$

# Rules of Thumb

1. **Amdahl/Case Rule**: A balanced computer system needs about 1 MB of main memory capacity and 1 megabit per second of I/O bandwidth per MIPS of CPU performance.
2. **90/10 Locality Rule**: A program executes about $90\%$ of its instructions in $10\%$ of its code.
3. **Bandwidth Rule**: Bandwidth grows by at least the square of the improvement in latency.
4. **2:1 Cache Rule**: The miss rate of a direct-mapped cache of size $N$ is about the same as a two-way set-associative cache of size $N/2$.
5. **Dependability Rule**: Design with no single point of failure.
6. **Watt-Year Rule**: The fully burdened cost of a Watt per year in a Warehouse Scale Computer in North America in 2011, including the cost of amortizing the power and cooling infrastructure, is about $\$2$.

---

<!-- page 2 -->

# An Overview of the Content

**Chapter 1** includes formulas for energy, static power, dynamic power, integrated circuit costs, reliability, and availability. (These formulas are also found on the front inside cover.) Our hope is that these topics can be used through the rest of the book. In addition to the classic quantitative principles of computer design and performance measurement, it shows the slowing of performance improvement of general-purpose microprocessors, which is one inspiration for domain-specific architectures.

Our view is that the instruction set architecture is playing less of a role today than in 1990, so we moved this material to **Appendix A**. It now uses the RISC-V architecture. (For quick review, a summary of the RISC-V ISA can be found on the back inside cover.) For fans of ISAs, **Appendix K** was revised for this edition and covers 8 RISC architectures (5 for desktop and server use and 3 for embedded use), the $80 \times 86$, the DEC VAX, and the IBM 360/370.

We then move onto memory hierarchy in **Chapter 2**, since it is easy to apply the cost-performance-energy principles to this material, and memory is a critical resource for the rest of the chapters. As in the past edition, **Appendix B** contains an introductory review of cache principles, which is available in case you need it. **Chapter 2** discusses 10 advanced optimizations of caches. The chapter includes virtual machines, which offer advantages in protection, software management, and hardware management, and play an important role in cloud computing. In addition to covering SRAM and DRAM technologies, the chapter includes new material both on Flash memory and on the use of stacked die packaging for extending the memory hierarchy. The PIAT examples are the ARM Cortex A8, which is used in PMDs, and the Intel Core i7, which is used in servers.

**Chapter 3** covers the exploitation of instruction-level parallelism in high-performance processors, including superscalar execution, branch prediction (including the new tagged hybrid predictors), speculation, dynamic scheduling, and simultaneous multithreading. As mentioned earlier, **Appendix C** is a review of pipelining in case you need it. **Chapter 3** also surveys the limits of ILP. Like **Chapter 2**, the PIAT examples are again the ARM Cortex A8 and the Intel Core i7. While the third edition contained a great deal on Itanium and VLIW, this material is now in **Appendix H**, indicating our view that this architecture did not live up to the earlier claims.

The increasing importance of multimedia applications such as games and video processing has also increased the importance of architectures that can exploit data level parallelism. In particular, there is a rising interest in computing using graphical processing units (GPUs), yet few architects understand how GPUs really work. We decided to write a new chapter in large part to unveil this new style of computer architecture. **Chapter 4** starts with an introduction to vector architectures, which acts as a foundation on which to build explanations of multimedia SIMD instruction set extensions and GPUs. (**Appendix G** goes into even more depth on vector architectures.) This chapter introduces the Roofline performance model and then uses it to compare the Intel Core i7 and the NVIDIA GTX 280 and GTX 480 GPUs. The chapter also describes the Tegra 2 GPU for PMDs.

Preface $\square$ xix

---

<!-- page 3 -->

\noindent $\text{XX} \quad \text{Preface}$

**Chapter 5** describes multicore processors. It explores symmetric and distributed-memory architectures, examining both organizational principles and performance. The primary additions to this chapter include more comparison of multicore organizations, including the organization of multicore-multilevel caches, multicore coherence schemes, and on-chip multicore interconnect. Topics in synchronization and memory consistency models are next. The example is the Intel Core i7. Readers interested in more depth on interconnection networks should read Appendix F, and those interested in larger scale multiprocessors and scientific applications should read Appendix I.

**Chapter 6** describes warehouse-scale computers (WSCs). It was extensively revised based on help from engineers at Google and Amazon Web Services. This chapter integrates details on design, cost, and performance of WSCs that few architects are aware of. It starts with the popular MapReduce programming model before describing the architecture and physical implementation of WSCs, including cost. The costs allow us to explain the emergence of cloud computing, whereby it can be cheaper to compute using WSCs in the cloud than in your local datacenter. The PIAT example is a description of a Google WSC that includes information published for the first time in this book.

The new **Chapter 7** motivates the need for Domain-Specific Architectures (DSAs). It draws guiding principles for DSAs based on the four examples of DSAs. Each DSA corresponds to chips that have been deployed in commercial settings. We also explain why we expect a renaissance in computer architecture via DSAs given that single-thread performance of general-purpose microprocessors has stalled.

This brings us to Appendices A through M. **Appendix A** covers principles of ISAs, including RISC-V, and **Appendix K** describes 64-bit versions of RISC V, ARM, MIPS, Power, and SPARC and their multimedia extensions. It also includes some classic architectures ($80\times 86$, VAX, and IBM 360/370) and popular embedded instruction sets (Thumb-2, microMIPS, and RISC V C). **Appendix H** is related, in that it covers architectures and compilers for VLIW ISAs.

As mentioned earlier, **Appendix B** and **Appendix C** are tutorials on basic caching and pipelining concepts. Readers relatively new to caching should read **Appendix B** before **Chapter 2**, and those new to pipelining should read **Appendix C** before **Chapter 3**.

**Appendix D**, “Storage Systems,” has an expanded discussion of reliability and availability, a tutorial on RAID with a description of RAID 6 schemes, and rarely found failure statistics of real systems. It continues to provide an introduction to queuing theory and I/O performance benchmarks. We evaluate the cost, performance, and reliability of a real cluster: the Internet Archive. The “Putting It All Together” example is the NetApp FAS6000 filer.

**Appendix E**, by Thomas M. Conte, consolidates the embedded material in one place.

**Appendix F**, on interconnection networks, is revised by Timothy M. Pinkston and José Duato. **Appendix G**, written originally by Krste Asanović, includes a description of vector processors. We think these two appendices are some of the best material we know of on each topic.

---

<!-- page 4 -->

Preface \hfill xxii

Appendix H describes VLIW and EPIC, the architecture of Itanium.
Appendix I describes parallel processing applications and coherence protocols
for larger-scale, shared-memory multiprocessing. Appendix J, by David Goldberg,
describes computer arithmetic.

Appendix L, by Abhishek Bhattacharjee, is new and discusses advanced tech-
niques for memory management, focusing on support for virtual machines and
design of address translation for very large address spaces. With the growth in
clouds processors, these architectural enhancements are becoming more important.

Appendix M collects the “Historical Perspective and References” from each
chapter into a single appendix. It attempts to give proper credit for the ideas in each
chapter and a sense of the history surrounding the inventions. We like to think of
this as presenting the human drama of computer design. It also supplies references
that the student of architecture may want to pursue. If you have time, we recom-
mend reading some of the classic papers in the field that are mentioned in these
sections. It is both enjoyable and educational to hear the ideas directly from the
creators. “Historical Perspective” was one of the most popular sections of prior
editions.

\medskip

### Navigating the Text

There is no single best order in which to approach these chapters and appendices,
except that all readers should start with Chapter 1. If you don't want to read every-
thing, here are some suggested sequences:

*   **Memory Hierarchy:** Appendix B, Chapter 2, and Appendices D and M.
*   **Instruction-Level Parallelism:** Appendix C, Chapter 3, and Appendix H
*   **Data-Level Parallelism:** Chapters 4, 6, and 7, Appendix G
*   **Thread-Level Parallelism:** Chapter 5, Appendices F and I
*   **Request-Level Parallelism:** Chapter 6
*   **ISA:** Appendices A and K

Appendix E can be read at any time, but it might work best if read after the ISA and
cache sequences. Appendix J can be read whenever arithmetic moves you. You
should read the corresponding portion of Appendix M after you complete each
chapter.

\medskip

### Chapter Structure

The material we have selected has been stretched upon a consistent framework that
is followed in each chapter. We start by explaining the ideas of a chapter. These
ideas are followed by a “Crosscutting Issues” section, a feature that shows how the
ideas covered in one chapter interact with those given in other chapters. This is

---

<!-- page 5 -->

`xxii` $\quad \bullet \quad$ Preface

followed by a “Putting It All Together” section that ties these ideas together by showing how they are used in a real machine.

Next in the sequence is “Fallacies and Pitfalls,” which lets readers learn from the mistakes of others. We show examples of common misunderstandings and architectural traps that are difficult to avoid even when you know they are lying in wait for you. The “Fallacies and Pitfalls” sections is one of the most popular sections of the book. Each chapter ends with a “Concluding Remarks” section.

### Case Studies With Exercises

Each chapter ends with case studies and accompanying exercises. Authored by experts in industry and academia, the case studies explore key chapter concepts and verify understanding through increasingly challenging exercises. Instructors should find the case studies sufficiently detailed and robust to allow them to create their own additional exercises.

Brackets for each exercise (`<chapter.section>`) indicate the text sections of primary relevance to completing the exercise. We hope this helps readers to avoid exercises for which they haven’t read the corresponding section, in addition to pro- viding the source for review. Exercises are rated, to give the reader a sense of the amount of time required to complete an exercise:

[10] Less than 5 min (to read and understand)
[15] 5–15 min for a full answer
[20] 15–20 min for a full answer
[25] 1 h for a full written answer
[30] Short programming project: less than 1 full day of programming
[40] Significant programming project: 2 weeks of elapsed time
[Discussion] Topic for discussion with others

Solutions to the case studies and exercises are available for instructors who register at **textbooks.elsevier.com**.

### Supplemental Materials

A variety of resources are available online at https://www.elsevier.com/books/computer-architecture/hennessy/978-0-12-811905-1, including the following:

* Reference appendices, some guest authored by subject experts, covering a range of advanced topics
* Historical perspectives material that explores the development of the key ideas presented in each of the chapters in the text

---

<!-- page 6 -->

# 1

## Fundamentals of Quantitative Design and Analysis

An iPod, a phone, an Internet mobile communicator... these are NOT three separate devices! And we are calling it iPhone! Today Apple is going to reinvent the phone. And here it is.

*Steve Jobs, January 9, 2007*

New information and communications technologies, in particular high-speed Internet, are changing the way companies do business, transforming public service delivery and democratizing innovation. With 10 percent increase in high speed Internet connections, economic growth increases by 1.3 percent.

*The World Bank, July 28, 2009*

---
Computer Architecture. https://doi.org/10.1016/B978-0-12-811905-1.00001-8
© 2019 Elsevier Inc. All rights reserved.

---

<!-- page 7 -->

## 1.1 Introduction

Computer technology has made incredible progress in the roughly 70 years since the first general-purpose electronic computer was created. Today, less than \$500 will purchase a cell phone that has as much performance as the world's fastest computer bought in 1993 for \$50 million. This rapid improvement has come both from advances in the technology used to build computers and from innovations in computer design.

Although technological improvements historically have been fairly steady, progress arising from better computer architectures has been much less consistent. During the first 25 years of electronic computers, both forces made a major contribution, delivering performance improvement of about 25% per year. The late 1970s saw the emergence of the microprocessor. The ability of the microprocessor to ride the improvements in integrated circuit technology led to a higher rate of performance improvement—roughly 35% growth per year.

This growth rate, combined with the cost advantages of a mass-produced microprocessor, led to an increasing fraction of the computer business being based on microprocessors. In addition, two significant changes in the computer market place made it easier than ever before to succeed commercially with a new architecture. First, the virtual elimination of assembly language programming reduced the need for object-code compatibility. Second, the creation of standardized, vendor-independent operating systems, such as UNIX and its clone, Linux, lowered the cost and risk of bringing out a new architecture.

These changes made it possible to develop successfully a new set of architectures with simpler instructions, called RISC (Reduced Instruction Set Computer) architectures, in the early 1980s. The RISC-based machines focused the attention of designers on two critical performance techniques, the exploitation of instruction-level parallelism (initially through pipelining and later through multiple instruction issue) and the use of caches (initially in simple forms and later using more sophisticated organizations and optimizations).

The RISC-based computers raised the performance bar, forcing prior architectures to keep up or disappear. The Digital Equipment Vax could not, and so it was replaced by a RISC architecture. Intel rose to the challenge, primarily by translating 80x86 instructions into RISC-like instructions internally, allowing it to adopt many of the innovations first pioneered in the RISC designs. As transistor counts soared in the late 1990s, the hardware overhead of translating the more complex x86 architecture became negligible. In low-end applications, such as cell phones, the cost in power and silicon area of the x86-translation overhead helped lead to a RISC architecture, ARM, becoming dominant.

Figure 1.1 shows that the combination of architectural and organizational enhancements led to 17 years of sustained growth in performance at an annual rate of over 50%—a rate that is unprecedented in the computer industry.

The effect of this dramatic growth rate during the 20th century was fourfold. First, it has significantly enhanced the capability available to computer users. For many applications, the highest-performance microprocessors outperformed the supercomputer of less than 20 years earlier.

---

<!-- page 8 -->

```markdown
1.1 Introduction $\square$ 3

[FIGURE: A semi-log plot showing processor performance over time, relative to the VAX 11/780, from 1978 to 2018. The y-axis is logarithmic (Performance relative to VAX 11/780, from 1 to 100,000) and the x-axis is linear (Year, from 1978 to 2018). Different performance growth rates (52%/year, 25%/year, 23%/year, 12%/year, 3.5%/year) are indicated by shaded regions.]

**Figure 1.1 Growth in processor performance over 40 years.** This chart plots program performance relative to the VAX 11/780 as measured by the SPEC integer benchmarks (see Section 1.8), growth in performance was largely technology-driven and averaged about $52\%$ per year, or doubling every $1.3$ years, prior to the mid-1980s. Growth in performance was largely technology-driven and averaged about $52\%$ per year, or doubling every $1.3$ years, prior to the mid-1980s. Growth in performance during this era was largely technology-driven and averaged about $52\%$ per year, or doubling every $1.3$ years. Prior to the mid-1980s, growth in performance was largely technology-driven and averaged about $52\%$ per year, or doubling every $1.4$ years, from $1978$ to $1986$, or doubling every $1.4$ years. The increase in growth to about $52\%$ starting in $1986$, or doubling every $1.4$ years, is attributable to architectural and organizational ideas typified in RISC architectures. By $2003$ this growth led to a performance factor of $25$ versus the performance that would have occurred if it had continued at the $22\%$ rate. In $2003$, this growth led to a performance factor of $25$ versus the performance that would have occurred if it had continued at the $22\%$ rate. In $2003$ this growth led to a performance factor of $25$ versus the performance that would have occurred if it had continued at the $22\%$ rate. In $2003$ this growth led to a performance factor of $25$ versus the performance that would have occurred if it had continued at the $22\%$ rate. In $2003$ this growth led to a performance factor of $25$ versus the performance that would have occurred if it had continued at the **$22\%$ rate**. In $2003$ this growth led to a performance factor of $25$ versus the performance that would have occurred if it had continued at the $22\%$ rate. Since $2003$ the scaling and the available instruction-level parallelism slowed uniprocessor performance to $23\%$ per year until $2011$, or doubling every $3.5$ years. These results are limited to single-chip systems with usually four cores per chip. From $2011$ to $2015$, the annual improvement has been just $3.5\%$ per year, or doubling every $20$ years. Since $2015$, with the parallelism of Amdahl's Law, since $2015$, with the parallelism of Amdahl's Law, since $2015$, with the parallelism of Amdahl's Law, since $2015$, with the parallelism of Amdahl's Law, since $2015$, with the parallelism of Amdahl's Law, performance for floating-point-oriented calculations in clock rates for these same stages, has changed over the years, performance of newer machines is estimated by a scaling factor that relates the performance for different versions of SPEC: SPEC95, SPEC92, SPEC95, SPEC2000, and SPEC2006. There are too few results for SPEC2017 to plot yet.
```

---

<!-- page 9 -->

**Chapter One Fundamentals of Quantitative Design and Analysis**

Second, this dramatic improvement in cost-performance led to new classes of computers. Personal computers and workstations emerged in the 1980s with the availability of the microprocessor. The past decade saw the rise of smart cell phones and tablet computers, which many people are using as their primary computing platforms instead of PCs. These mobile client devices are increasingly using the Internet to access warehouses containing 100,000 servers, which are being designed as if they were a single gigantic computer.

Third, improvement of semiconductor manufacturing as predicted by Moore's law has led to the dominance of microprocessor-based computers across the entire range of computer design. Minicomputers, which were traditionally made from off-the-shelf logic or from gate arrays, were replaced by servers made by using microprocessors. Even mainframe computers and high-performance supercomputers are all collections of microprocessors.

The preceding hardware innovations led to a renaissance in computer design, which emphasized both architectural innovation and efficient use of technology improvements. This rate of growth compounded so that by 2003, highperformance microprocessors were $7.5$ times as fast as what would have been obtained by relying solely on technology, including improved circuit design, that is, $52\%$ per year versus $35\%$ per year.

This hardware renaissance led to the fourth impact, which was on software development. This 50,000-fold performance improvement since 1978 (see Figure 1.1) allowed modern programmers to trade performance for productivity. In place of performance-oriented languages like C and C++, much more programming today is done in managed programming languages like Java and Scala. Moreover, scripting languages like JavaScript and Python, which are even more productive, are gaining in popularity along with programming frameworks like AngularJS and Django. To maintain productivity and try to close the performance gap, interpreters with just-in-time compilers and trace-based compiling are replacing the traditional compiler and linker of the past. Software deployment is changing as well, with Software as a Service (SaaS) used over the Internet replacing shrink-wrapped software that must be installed and run on a local computer.

The nature of applications is also changing. Speech, sound, images, and video are becoming increasingly important, along with predictable response time that is so critical to the user experience. An inspiring example is Google Translate. This application lets you hold up your cell phone to point its camera at an object, and the image is sent wirelessly over the Internet to a warehouse-scale computer (WSC) that recognizes the text in the photo and translates it into your native language. You can also speak into it, and it will translate what you said into audio output in another language. It translates text in 90 languages and voice in 15 languages. Alas, Figure 1.1 also shows that this 17-year hardware renaissance is over. The fundamental reason is that two characteristics of semiconductor processes that were true for decades no longer hold.

In 1974 Robert Dennard observed that power density was constant for a given area of silicon even as you increased the number of transistors because of smaller dimensions of each transistor. Remarkably, transistors could go faster but use less

---

<!-- page 10 -->

1.1 Introduction $\square$ 5

power. Dennard scaling ended around 2004 because current and voltage couldn't keep dropping and still maintain the dependability of integrated circuits.

This change forced the microprocessor industry to use multiple efficient processors or cores instead of a single inefficient processor. Indeed, in 2004 Intel canceled its high-performance uniprocessor projects and joined others in declaring that the road to higher performance would be via multiple processors per chip rather than via faster uniprocessors. This milestone signaled a historic switch from relying solely on instruction-level parallelism (ILP), the primary focus of the first three editions of this book, to *data-level parallelism* (DLP) and *thread-level parallelism* (TLP), which were featured in the fourth edition and expanded in the fifth edition. The fifth edition also added *WSCs* and *request-level parallelism* (RLP), which is expanded in this edition. Whereas the compiler and hardware conspire to exploit ILP implicitly without the programmer's attention, DLP, TLP, and RLP are explicitly parallel, requiring the restructuring of the application so that it can exploit explicit parallelism. In some instances, this is easy; in many, it is a major new burden for programmers.

Amdahl's Law (Section 1.9) prescribes practical limits to the number of useful cores per chip. If 10% of the task is serial, then the maximum performance benefit from parallelism is 10 no matter how many cores you put on the chip.

The second observation that ended recently is *Moore's Law*. In 1965 Gordon Moore famously predicted that the number of transistors per chip would double every year, which was amended in 1975 to every two years. That prediction lasted for about 50 years, but no longer holds. For example, in the 2010 edition of this book, the most recent Intel microprocessor had $1,170,000,000$ transistors. If Moore's Law had continued, we could have expected microprocessors in 2016 to have $18,720,000,000$ transistors. Instead, the equivalent Intel microprocessor has just $1,750,000,000$ transistors, or off by a factor of 10 from what Moore's Law would have predicted.
The combination of
* transistors no longer getting much better because of the slowing of Moore's Law and the end of Dennard scaling,
* the unchanging power budgets for microprocessors,
* the replacement of the single power-hungry processor with several energy-efficient processors, and
* the limits to multiprocessing to achieve Amdahl's Law

caused improvements in processor performance to slow down, that is, to *double* every 20 years, rather than every 1.5 years as it did between 1986 and 2003 (see Figure 1.1).

The only path left to improve energy-performance-cost is specialization. Future microprocessors will include several domain-specific cores that perform only one class of computations well, but they do so remarkably better than general-purpose cores. The new Chapter 7 in this edition introduces *domain-specific architectures*.

---

<!-- page 11 -->

# Chapter One Fundamentals of Quantitative Design and Analysis

This text is about the architectural ideas and accompanying compiler improvements that made the incredible growth rate possible over the past century, the reasons for the dramatic change, and the challenges and initial promising approaches to architectural ideas, compilers, and interpreters for the 21st century. At the core is a quantitative approach to computer design and analysis that uses empirical observations of programs, experimentation, and simulation as its tools. It is this style and approach to computer design that is reflected in this text. The purpose of this chapter is to lay the quantitative foundation on which the following chapters and appendices are based.

This book was written not only to explain this design style but also to stimulate you to contribute to this progress. We believe this approach will serve the computers of the future just as it worked for the implicitly parallel computers of the past.

## 1.2 Classes of Computers

These changes have set the stage for a dramatic change in how we view computing, computing applications, and the computer markets in this new century. Not since the creation of the personal computer have we seen such striking changes in the way computers appear and in how they are used. These changes in computer use have led to five diverse computing markets, each characterized by different applications, requirements, and computing technologies. Figure 1.2 summarizes these mainstream classes of computing environments and their important characteristics.

### Internet of Things/Embedded Computers

Embedded computers are found in everyday machines: microwaves, washing machines, most printers, networking switches, and all automobiles. The phrase

| Feature | Personal mobile device (PMD) | Desktop | Server | Clusters/warehouse-scale computer | Internet of things/ embedded |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Price of system | \$100–\$1000 | \$300–\$2500 | \$5000–\$10,000,000 | \$100,000–\$200,000,000 | \$10–\$100,000 |
| Price of microprocessor | \$10–\$100 | \$50–\$500 | \$200–\$2000 | \$50–\$250 | \$0.01–\$100 |
| Critical system design issues | Cost, energy, media performance, responsiveness | Priceperformance, energy, graphics performance | Throughput, availability, scalability, energy | Price-performance, throughput, energy proportionality | Price, energy, application-specific performance |

**Figure 1.2** A summary of the five mainstream computing classes and their system characteristics. Sales in 2015 included about 1.6 billion PMDs (90% cell phones), 275 million desktop PCs, and 15 million servers. The total number of embedded processors sold was nearly 19 billion. In total, 14.8 billion ARM-technology-based chips were shipped in 2015. Note the wide range in system price for servers and embedded systems, which go from USB keys to network routers. For servers, this range arises from the need for very large-scale multiprocessor systems for high-end trans-

---

<!-- page 12 -->

1.2 Classes of Computers $\square$ 7

Internet of Things (IoT) refers to embedded computers that are connected to the Internet, typically wirelessly. When augmented with sensors and actuators, IoT devices collect useful data and interact with the physical world, leading to a wide variety of "smart" applications, such as smart watches, smart thermostats, smart speakers, smart cars, smart homes, smart grids, and smart cities.

Embedded computers have the widest spread of processing power and cost. They include 8-bit to 32-bit processors that may cost one penny, and high-end 64-bit processors for cars and network switches that cost $\$100$. Although the range of computing power in the embedded computing market is very large, price is a key factor in the design of computers for this space. Performance requirements do exist, of course, but the primary goal often meets the performance need at a minimum price, rather than achieving more performance at a higher price. The projections for the number of IoT devices in 2020 range from 20 to 50 billion.

Most of this book applies to the design, use, and performance of embedded processors, whether they are off-the-shelf microprocessors or microprocessor cores that will be assembled with other special-purpose hardware.

Unfortunately, the data that drive the quantitative design and evaluation of other classes of computers have not yet been extended successfully to embedded computing (see the challenges with EEMBC, for example, in Section 1.8). Hence we are left for now with qualitative descriptions, which do not fit well with the rest of the book. As a result, the embedded material is concentrated in Appendix E. We believe a separate appendix improves the flow of ideas in the text while allowing readers to see how the differing requirements affect embedded computing.

### Personal Mobile Device

Personal mobile device (PMD) is the term we apply to a collection of wireless devices with multimedia user interfaces such as cell phones, tablet computers, and so on. Cost is a prime concern given the consumer price for the whole product is a few hundred dollars. Although the emphasis on energy efficiency is frequently driven by the use of batteries, the need to use less expensive packaging—plastic versus ceramic—and the absence of a fan for cooling also limit total power consumption. We examine the issue of energy and power in more detail in Section 1.5. Applications on PMDs are often web-based and media-oriented, like the previously mentioned Google Translate example. Energy and size requirements lead to use of Flash memory for storage (Chapter 2) instead of magnetic disks.

The processors in a PMD are often considered embedded computers, but we are keeping them as a separate category because PMDs are platforms that can run externally developed software, and they share many of the characteristics of desktop computers. Other embedded devices are more limited in hardware and software sophistication. We use the ability to run third-party software as the dividing line between nonembedded and embedded computers.

Responsiveness and predictability are key characteristics for media applications. A real-time performance requirement means a segment of the application has an absolute maximum execution time. For example, in playing a video on a

---

<!-- page 13 -->

**8** $\square$ **Chapter One Fundamentals of Quantitative Design and Analysis**

PMD, the time to process each video frame is limited, since the processor must accept and process the next frame shortly. In some applications, a more nuanced requirement exists: the average time for a particular task is constrained as well as the number of instances when some maximum time is exceeded. Such approaches—sometimes called $soft$ $real-time$—arise when it is possible to miss the time constraint on an event occasionally, as long as not too many are missed. Real-time performance tends to be highly application-dependent.

Other key characteristics in many PMD applications are the need to minimize memory and the need to use energy efficiently. Energy efficiency is driven by both battery power and heat dissipation. The memory can be a substantial portion of the system cost, and it is important to optimize memory size in such cases. The impor- tance of memory size translates to an emphasis on code size, since data size is dic- tated by the application.

### Desktop Computing

The first, and possibly still the largest market in dollar terms, is desktop computing. Desktop computing spans from low-end netbooks that sell for under $\$300$ to high- end, heavily configured workstations that may sell for $\$2500$. Since 2008, more than half of the desktop computers made each year have been battery operated lap- top computers. Desktop computing sales are declining.

Throughout this range in price and capability, the desktop market tends to be driven to optimize $price-performance$. This combination of performance (measured primarily in terms of compute performance and graphics perfor- mance) and price of a system is what matters most to customers in this market, and hence to computer designers. As a result, the newest, highest-performance microprocessors and cost-reduced microprocessors often appear first in desktop systems (see Section 1.6 for a discussion of the issues affecting the cost of computers).

Desktop computing also tends to be reasonably well characterized in terms of applications and benchmarking, though the increasing use of web-centric, interac- tive applications poses new challenges in performance evaluation.

### Servers

As the shift to desktop computing occurred in the 1980s, the role of servers grew to provide larger-scale and more reliable file and computing services. Such servers have become the backbone of large-scale enterprise computing, replacing the tra- ditional mainframe.

For servers, different characteristics are important. First, availability is critical. (We discuss availability in Section 1.7.) Consider the servers running ATM machines for banks or airline reservation systems. Failure of such server systems is far more catastrophic than failure of a single desktop, since these servers must operate seven days a week, 24 hours a day. Figure 1.3 estimates revenue costs of downtime for server applications.

---

<!-- page 14 -->

## 1.2 Classes of Computers $\blacksquare$ **9**

| Application | Cost of downtime per hour | \multicolumn{3}{|c|}{Annual losses with downtime of} |
| :--- | :--- | :--- | :--- | :--- |
| | | **1\%** (87.6 h/year) | **0.5\%** (43.8 h/year) | **0.1\%** (8.8 h/year) |
| Brokerage service | $\$4,000,000$ | $\$350,400,000$ | $\$175,200,000$ | $\$35,000,000$ |
| Energy | $\$1,750,000$ | $\$153,300,000$ | $\$76,700,000$ | $\$15,300,000$ |
| Telecom | $\$1,250,000$ | $\$109,500,000$ | $\$54,800,000$ | $\$11,000,000$ |
| Manufacturing | $\$1,000,000$ | $\$87,600,000$ | $\$43,800,000$ | $\$8,800,000$ |
| Retail | $\$650,000$ | $\$56,900,000$ | $\$28,500,000$ | $\$5,700,000$ |
| Health care | $\$400,000$ | $\$35,000,000$ | $\$17,500,000$ | $\$3,500,000$ |
| Media | $\$50,000$ | $\$4,400,000$ | $\$2,200,000$ | $\$400,000$ |

**Figure 1.3** Costs rounded to nearest $\$100,000$ of an unavailable system are shown by analyzing the cost of downtime (in terms of immediately lost revenue), assuming three different levels of availability, and that downtime is distributed uniformly. These data are from Landstrom (2014) and were collected and analyzed by Contingency Planning Research.

A second key feature of server systems is scalability. Server systems often grow in response to an increasing demand for the services they support or an expansion in functional requirements. Thus the ability to scale up the computing capacity, the memory, the storage, and the I/O bandwidth of a server is crucial. Finally, servers are designed for efficient throughput. That is, the overall performance of the server—in terms of transactions per minute or web pages served per second—is what is crucial. Responsiveness to an individual request remains important, but overall efficiency and cost-effectiveness, as determined by how many requests can be handled in a unit time, are the key metrics for most servers. We return to the issue of assessing performance for different types of computing environments in Section 1.8.

### Clusters/Warehouse-Scale Computers

The growth of Software as a Service (SaaS) for applications like search, social networking, video viewing and sharing, multiplayer games, online shopping, and so on has led to the growth of a class of computers called *clusters*. Clusters are collections of desktop computers or servers connected by local area networks to act as a single larger computer. Each node runs its own operating system, and nodes communicate using a networking protocol. WSCs are the largest of the clusters, in that they are designed so that tens of thousands of servers can act as one. Chapter 6 describes this class of extremely large computers.

Price-performance and power are critical to WSCs since they are so large. As Chapter 6 explains, the majority of the cost of a warehouse is associated with power and cooling of the computers inside the warehouse. The annual amortized cost of the computers themselves and the networking gear cost for a WSC is $\$40$ million, because they are usually replaced every few years. When you are buying that

---

<!-- page 15 -->

10 $\square$ Chapter One Fundamentals of Quantitative Design and Analysis

much computing, you need to buy wisely, because a $10\%$ improvement in price-
performance means an annual savings of $\$4$ million ($10\%$ of $\$40$ million) per
WSC; a company like Amazon might have 100 WSCs!
WSCs are related to servers in that availability is critical. For example, Ama-
zon.com had $\$136$ billion in sales in 2016. As there are about 8800 hours in a year,
the average revenue per hour was about $\$15$ million. During a peak hour for Christ-
mas shopping, the potential loss would be many times higher. As Chapter 6
explains, the difference between WSCs and servers is that WSCs use redundant,
inexpensive components as the building blocks, relying on a software layer to
catch and isolate the many failures that will happen with computing at this scale
to deliver the availability needed for such applications. Note that scalability for a
WSC is handled by the local area network connecting the computers and not by
integrated computer hardware, as in the case of servers.
*Supercomputers* are related to WSCs in that they are equally expensive,
costing hundreds of millions of dollars, but supercomputers differ by empha-
sizing floating-point performance and by running large, communication-intensive
batch programs that can run for weeks at a time. In contrast, WSCs emphasize
interactive applications, large-scale storage, dependability, and high Internet
bandwidth.

## Classes of Parallelism and Parallel Architectures

Parallelism at multiple levels is now the driving force of computer design across all
four classes of computers, with energy and cost being the primary constraints.
There are basically two kinds of parallelism in applications:

1. Data-level parallelism ($DLP$) arises because there are many data items that can
be operated on at the same time.
2. Task-level parallelism ($TLP$) arises because tasks of work are created that can
operate independently and largely in parallel.

Computer hardware in turn can exploit these two kinds of application parallelism in
four major ways:

1. Instruction-level parallelism exploits data-level parallelism at modest levels
with compiler help using ideas like pipelining and at medium levels using ideas
like speculative execution.
2. Vector architectures, graphic processor units ($GPUs$), and multimedia instruc-
tion sets exploit data-level parallelism by applying a single instruction to a col-
lection of data in parallel.
3. Thread-level parallelism exploits either data-level parallelism or task-level par-
allelism in a tightly coupled hardware model that allows for interaction between
parallel threads.
4. Request-level parallelism exploits parallelism among largely decoupled tasks
specified by the programmer or the operating system.

---

<!-- page 16 -->

1.3 Defining Computer Architecture $\qquad$ 11

When Flynn (1966) studied the parallel computing efforts in the 1960s, he found a simple classification whose abbreviations we still use today. They target data-level parallelism and task-level parallelism. He looked at the parallelism in the instruction and data streams called for by the instructions in the most constrained component of the multiprocessor and placed all computers in one of four categories:

1. Single instruction stream, single data stream (SISD)---This category is the uni- processor. The programmer thinks of it as the standard sequential computer, but it can exploit ILP. Chapter 3 covers SISD architectures that use ILP techniques such as superscalar and speculative execution.

2. Single instruction stream, multiple data streams (SIMD)---The same instruc- tion is executed by multiple processors using different data streams. SIMD com- puters exploit data-level parallelism by applying the same operations to multiple items of data in parallel. Each processor has its own data memory (hence, the MD of SIMD), but there is a single instruction memory and control processor, which fetches and dispatches instructions. Chapter 4 covers DLP and three different architectures that exploit it: vector architectures, multimedia extensions to standard instruction sets, and GPUs.

3. Multiple instruction streams, single data stream (MISD)---No commercial mul- tiprocessor of this type has been built to date, but it rounds out this simple classification.

4. Multiple instruction streams, multiple data streams (MIMD)---Each processor fetches its own instructions and operates on its own data, and it targets task-level parallelism. In general, MIMD is more flexible than SIMD and thus more gen- erally applicable, but it is inherently more expensive than SIMD. For example, MIMD computers can also exploit data-level parallelism, although the overhead is likely to be higher than would be seen in an SIMD computer. This overhead means that grain size must be sufficiently large to exploit the parallelism effi- ciently. Chapter 5 covers tightly coupled MIMD architectures, which exploit thread-level parallelism because multiple cooperating threads operate in paral- lel. Chapter 6 covers loosely coupled MIMD architectures---specifically, clus- ters and warehouse-scale computers---that exploit request-level parallelism, where many independent tasks can proceed in parallel naturally with little need for communication or synchronization.

This taxonomy is a coarse model, as many parallel processors are hybrids of the SISD, SIMD, and MIMD classes. Nonetheless, it is useful to put a framework on the design space for the computers we will see in this book.

---
1.3 Defining Computer Architecture

The task the computer designer faces is a complex one: determine what attributes are important for a new computer, then design a computer to maximize

---

<!-- page 17 -->

12 $\quad$ Chapter One Fundamentals of Quantitative Design and Analysis

performance and energy efficiency while staying within cost, power, and availabil-
ity constraints. This task has many aspects, including instruction set design, func-
tional organization, logic design, and implementation. The implementation may
encompass integrated circuit design, packaging, power, and cooling. Optimizing
the design requires familiarity with a very wide range of technologies, from com-
pilers and operating systems to logic design and packaging.

A few decades ago, the term *computer architecture* generally referred to only
instruction set design. Other aspects of computer design were called implementa-
tion, often insinuating that implementation is uninteresting or less challenging.

We believe this view is incorrect. The architect’s or designer’s job is much
more than instruction set design, and the technical hurdles in the other aspects
of the project are likely more challenging than those encountered in instruction
set design. We’ll quickly review instruction set architecture before describing
the larger challenges for the computer architect.

### Instruction Set Architecture: The Myopic View
of Computer Architecture

We use the term *instruction set architecture* (ISA) to refer to the actual
programmer-visible instruction set in this book. The ISA serves as the boundary
between the software and hardware. This quick review of ISA will use examples
from 80x86, ARMv8, and RISC-V to illustrate the seven dimensions of an ISA.
The most popular RISC processors come from ARM (Advanced RISC Machine),
which were in 14.8 billion chips shipped in 2015, or roughly 50 times as many
chips that shipped with 80x86 processors. Appendices A and K give more details
on the three ISAs.

RISC-V (“RISC Five”) is a modern RISC instruction set developed at the
University of California, Berkeley, which was made free and openly adoptable
in response to requests from industry. In addition to a full software stack (com-
pilers, operating systems, and simulators), there are several RISC-V implementa-
tions freely available for use in custom chips or in field-programmable gate arrays.
Developed 30 years after the first RISC instruction sets, RISC-V inherits its ances-
tors’ good ideas—a large set of registers, easy-to-pipeline instructions, and a lean
set of operations—while avoiding their omissions or mistakes. It is a free and
open, elegant example of the RISC architectures mentioned earlier, which is
why more than 60 companies have joined the RISC-V Foundation, including
AMD, Google, HP Enterprise, IBM, Microsoft, Nvidia, Qualcomm, Samsung,
and Western Digital. We use the integer core ISA of RISC-V as the example
ISA in this book.

1. **Class of ISA**—Nearly all ISAs today are classified as general-purpose register
architectures, where the operands are either registers or memory locations. The
80x86 has 16 general-purpose registers and 16 that can hold floating-point data,
while RISC-V has 32 general-purpose and 32 floating-point registers (see
Figure 1.4). The two popular versions of this class are *register-memory* ISAs,

---

<!-- page 18 -->

1.3 Defining Computer Architecture $\blacksquare$ 13

| Register | Name | Use | Saver |
| :--- | :--- | :--- | :--- |
| x0 | zero | The constant value 0 | N.A. |
| x1 | ra | Return address | Caller |
| x2 | sp | Stack pointer | Callee |
| x3 | gp | Global pointer | - |
| x4 | tp | Thread pointer | - |
| x5-x7 | t0-t2 | Temporaries | Caller |
| x8 | s0/fp | Saved register/frame pointer | Callee |
| x9 | s1 | Saved register | Callee |
| x10-x11 | a0-a1 | Function arguments/return values | Caller |
| x12-x17 | a2-a7 | Function arguments | Caller |
| x18-x27 | s2-s11 | Saved registers | Callee |
| x28-x31 | t3-t6 | Temporaries | Caller |
| f0-f7 | ft0-ft7 | FP temporaries | Caller |
| f8-f9 | fs0-fs1 | FP saved registers | Callee |
| f10-f11 | fa0-fa1 | FP function arguments/return values | Caller |
| f12-f17 | fa2-fa7 | FP function arguments | Caller |
| f18-f27 | fs2-fs11 | FP saved registers | Callee |
| f28-f31 | ft8-ft11 | FP temporaries | Caller |

[FIGURE: RISC-V registers, names, usage, and calling conventions.] RISC-V has 32 general-purpose registers (x0-x31), RISC-V has 32 floating-point registers (f0-f31) that can hold either a 32-bit single-precision number or a 64-bit double-precision number. The registers that are preserved across a procedure call are labeled "Callee" saved.

such as the $80\text{x}86$, which can access memory as part of many instructions, and load-store ISAs, such as ARMv8 and RISC-V, which can access memory only with load or store instructions. All ISAs announced since 1985 are load-store.

2. Memory addressing—Virtually all desktop and server computers, including the $80\text{x}86$, ARMv8, and RISC-V, use byte addressing to access memory operands. Some architectures, like ARMv8, require that objects must be *aligned*. An access to an object of size $s$ bytes at byte address $A$ is aligned if $A \pmod s = 0$. (See Figure A.5 on page A-8.) The $80\text{x}86$ and RISC-V do not require alignment, but accesses are generally faster if operands are aligned.

3. Addressing modes—In addition to specifying registers and constant operands, addressing modes specify the address of a memory object. RISC-V addressing modes are Register, Immediate (for constants), and Displacement, where a constant offset is added to a register to form the memory address. The $80\text{x}86$ supports those three modes, plus three variations of displacement: no register (absolute), two registers (based indexed with displacement), and two registers

---

<!-- page 19 -->

14 $\quad$ Chapter One Fundamentals of Quantitative Design and Analysis

where one register is multiplied by the size of the operand in bytes (based with scaled index and displacement). It has more like the last three modes, minus the displacement field, plus register indirect, indexed, and based with scaled index. ARMv8 has three RISC-V addressing modes plus PC-relative addressing, the sum of two registers, and the sum of two registers where one register is multiplied by the size of the operand in bytes. It also has autoincrement and autodecrement addressing, where the calculated address replaces the contents of one of the registers used in forming the address.

4. **Types and sizes of operands**—Like most ISAs, 80x86, ARMv8, and RISC-V support operand sizes of 8-bit (ASCII character), 16-bit (Unicode character or half word), 32-bit (integer or word), 64-bit (double word or long integer), and IEEE 754 floating point in 32-bit (single precision) and 64-bit (double precision). The 80x86 also supports 80-bit floating point (extended double precision).

5. **Operations**—The general categories of operations are data transfer, arithmetic, logical, control (discussed next), and floating point. RISC-V is a simple and easy-to-pipeline instruction set architecture, and it is representative of the RISC architectures being used in 2017. Figure 1.5 summarizes the integer RISC-V ISA, and Figure 1.6 lists the floating-point ISA. The 80x86 has a much richer and larger set of operations (see Appendix K).

6. **Control flow instructions**—Virtually all ISAs, including these three, support conditional branches, unconditional jumps, procedure calls, and returns. All three use PC-relative addressing, where the branch address is specified by an address field that is added to the PC. There are some small differences. RISC-V conditional branches ($\text{BE}, \text{BNE}$, etc.) test the contents of registers, and the 80x86 and ARMv8 branches test condition code bits set as side effects of arithmetic/logic operations. The ARMv8 and RISC-V procedure call places the return address in a register, whereas the 80x86 call ($\text{CALLF}$) places the return address on a stack in memory.

7. **Encoding an ISA**—There are two basic choices on encoding: *fixed length* and *variable length*. All ARMv8 and RISC-V instructions are 32 bits long, which simplifies instruction decoding. Figure 1.7 shows the RISC-V instruction formats. The 80x86 encoding is variable length, ranging from 1 to 15 bytes. Variable-length instructions can take less space than fixed-length instructions, so a program compiled for the 80x86 is usually smaller than the same program compiled for RISC-V. Note that choices mentioned previously will affect how the instructions are encoded into a binary representation. For example, the number of registers and the number of addressing modes both have a significant impact on the size of instructions, because the register field and addressing mode field can appear many times in a single instruction. (Note that ARMv8 and RISC-V later offered extensions, called Thumb-2 and RV64IC, that provide a mix of 16-bit and 32-bit length instructions, respectively, to reduce program size. Code size for these compact versions of RISC architectures are smaller than that of the 80x86. See Appendix K.)

---

<!-- page 20 -->

1.3 Defining Computer Architecture $\square$ 15

| Instruction type/opcode | Instruction meaning |
| :--- | :--- |
| **Data transfers** | Move data between registers and memory, or between the integer and FP or special registers; only memory address mode is 12-bit displacement+contents of a GPR |
| `lb, lbu, sb` | Load byte, load byte unsigned, store byte (to/from integer registers) |
| `lh, lhu, sh` | Load half word, load half word unsigned, store half word (to/from integer registers) |
| `lw, lwu, sw` | Load word, load word unsigned, store word (to/from integer registers) |
| `ld, sd` | Load double word, store double word (to/from integer registers) |
| `flw, fld, fsw, fsd` | Load SP float, load DP float, store SP float, store DP float |
| `fmv._x., fmv._x._` | Copy from/to integer register to/from floating-point register; "$\_\_$" for single-precision, D for double-precision |
| `csrrw, csrrs, csrrsi, csrrcc, csrrc` | Read counters and write status registers, which include counters: clock cycles, time, instructions retired |
| **Arithmetic/logical** | Operations on integer or logical data in GPRs |
| `add, addi, addw, addiw` | Add, add immediate (all immediates are 12 bits), add 32-bits only & sign-extend to 64 bits, add immediate 32-bits only |
| `sub, subw` | Subtract, subtract 32-bits only |
| `mul, mulw, mulh, mulhsu, mulhu` | Multiply, multiply 32-bits only, multiply upper half, multiply upper half signed, multiply upper half unsigned |
| `div, divu, rem, remu` | Divide, divide unsigned, remainder, remainder unsigned |
| `divw, divuw, remw, remuw` | Divide and remainder: as previously, but divide only lower 32-bits, producing 32-bit sign-extended result |
| `and, andi` | And, and immediate |
| `or, ori, xor, xori` | Or, or immediate, exclusive or, or exclusive or immediate |
| `lui` | Load upper immediate; loads bits 31-12 of register with immediate, then sign-extends |
| `auipc` | Adds immediate in bits 31-12 with zeros in lower bits to PC; used with JALR to transfer control to any 32-bit address |
| `sll, slli, srl, srli, sra, srai` | Shifts: shift left logical, right logical, right arithmetic; both variable and immediate forms |
| `sllw, slliw, srlw, srliw, sraw, sraiw` | Shifts: as previously, but shift lower 32-bits, producing 32-bit sign-extended result |
| `slt, slti, sltu, sltiu` | Set less than, set less than immediate, signed and unsigned |
| **Control** | Conditional branches and jumps; PC-relative or through register |
| `beq, bne, blt, bge, bltu, bgeu` | Branch GPR equal/not equal; less than; greater than or equal, signed and unsigned |
| `jal, jalr` | Jump and link: save PC+4, target is PC-relative (`JAL`) or a register (`JALR`); if specify $\text{x}0$ as destination register, then acts as a simple jump |
| `ecall` | Make a request to the supporting execution environment, which is usually an OS |
| `ebreak` | Debuggers used to cause control to be transferred back to a debugging environment |
| `fence, fence.i` | Synchronize threads to guarantee ordering of memory accesses; synchronize instructions and data for stores to instruction memory |

Figure 1.5 Subset of the instructions in RISC-V. RISC-V has a base set of instructions ($\text{R}64\text{I}$) and offers optional extensions: multiply-divide ($\text{RVM}$), single-precision floating point ($\text{RVF}$), double-precision floating point ($\text{RVD}$). This figure includes $\text{RVM}$ and the next one shows $\text{RVF}$ and $\text{RVD}$. Appendix A gives much more detail on RISC-V.

---

<!-- page 21 -->

# 16 $\quad$ Chapter One Fundamentals of Quantitative Design and Analysis

| Instruction type/opcode | Instruction meaning |
| :--- | :--- |
| **Floating point** | **FP operations on DP and SP formats** |
| `fadd.d`, `fadd.s` | Add DP, SP numbers |
| `fsub.d`, `fsub.s` | Subtract DP, SP numbers |
| `fmul.d`, `fmul.s` | Multiply DP, SP floating point |
| `fmadd.d`, `fmadd.s`, `fnmadd.d`, `fnmadd.s` | Multiply-add DP, SP numbers; negative multiply-add DP, SP numbers |
| `fmsub.d`, `fmsub.s`, `fnmsub.d`, `fnmsub.s` | Multiply-sub DP, SP numbers; negative multiply-sub DP, SP numbers |
| `fdiv.d`, `fdiv.s` | Divide DP, SP floating point |
| `fsqrt.d`, `fsqrt.s` | Square root DP, SP floating point |
| `fmax.d`, `fmax.s`, `fmin.d`, `fmin.s` | Maximum and minimum DP, SP floating point |
| `fcvt.`, `fcvt._.u`, `fcvt._.l`, `fcvt._.w`, `fcvt._.lu`, `fcvt._.uw` | Convert instructions: `FCVT.x.y` converts from type $x$ to type $y$, where $x$ and $y$ are $\text{L}$ (64-bit integer), $\text{W}$ (32-bit integer), $\text{D}$ (DP), or $\text{S}$ (SP). Integers can be unsigned ($\text{U}$). |
| `feq._`, `flt._`, `fle._` | Floating-point compare between floating-point registers and record the Boolean result in integer register: “$\_=\text{S}$” for single-precision, “$\_=\text{D}$” for double-precision |
| `fclass.d`, `fclass.s` | Writes to integer register a 10-bit mask that indicates the class of the floating-point number ($-\infty$, $+\infty$, $-0$, $+0$, $\text{NaN}$, $\dots$) |
| `fsgnj._`, `fsgnjn._`, `fsgnjx._` | Sign-injection instructions that changes only the sign bit: copy sign bit from other source, the opposite of sign bit of other source, XOR of the 2 sign bits |

**Figure 1.6** Floating point instructions for RISC-V. RISC-V has a base set of instructions (R64I) and offers optional extensions for single-precision floating point (RVF) and double-precision floating point (RVD). $\text{SP}$ = single precision; $\text{DP}$ = double precision.

| 31 | 25 24 | 20 19 | 15 14 12 11 | 7 6 | 0 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `funct7` | `rs2` | `rs1` | `funct3` | `rd` | `opcode` | R-type |
| | `imm [11:0]` | `rs1` | `funct3` | `rd` | `opcode` | I-type |
| | `imm [11:5]` | `rs2` | `rs1` | `funct3` | `imm [4:0]` | `opcode` | S-type |
| | `imm [12]` | `imm [10:5]` | `rs2` | `rs1` | `funct3` | `imm [4:1|11]` | `opcode` | B-type |
| | | | `imm [31:12]` | `rd` | `opcode` | U-type |
| | `imm [20|10:1|11|19:12]` | | | `rd` | `opcode` | J-type |

**Figure 1.7** The base RISC-V instruction set architecture formats. All instructions are 32 bits long. The $\text{R}$ format is for integer register-to-register operations, such as $\text{ADD}$, $\text{SUB}$, and so on. The $\text{I}$ format is for loads and immediate operations, such as $\text{LD}$ and $\text{ADDI}$. The $\text{B}$ format is for branches and the $\text{J}$ format is for jumps and link. The $\text{S}$ format is for stores. Having a separate format for stores allows the three register specifiers ($\text{rd}$, $\text{rs1}$, $\text{rs2}$) to always be in the same location in all formats. The $\text{U}$ format is for the wide immediate instructions ($\text{LUI}$, $\text{AUPIC}$).

---

<!-- page 22 -->

1.3 Defining Computer Architecture $\square$ 17

The other challenges facing the computer architect beyond ISA design are par\- ticularly acute at the present, when the differences among instruction sets are small and when there are distinct application areas. Therefore, starting with the fourth edition of this book, beyond this quick review, the bulk of the instruction mate\- rial is found in the appendices (see Appendices A and K).

## Genuine Computer Architecture: Designing the Organization and Hardware to Meet Goals and Functional Requirements

The implementation of a computer has two components: organization and hard\- ware. The term *organization* includes the high-level aspects of a computer’s design, such as the memory system, the memory interconnect, and the design of the internal processor or CPU (central processing unit—where arithmetic, logic, branching, and data transfer are implemented). The term *microarchitecture* is also used instead of organization. For example, two processors with the same instruc\- tion set architectures but different organizations are the AMD Opteron and the Intel Core i7. Both processors implement the $80\times 86$ instruction set, but they have very different pipeline and cache organizations.

The switch to multiple processors per microprocessor led to the term *core* also being used for processors. Instead of saying multiprocessor microprocessor, the term *multicore* caught on. Given that virtually all chips have multiple processors, the term central processing unit, or CPU, is fading in popularity.

*Hardware* refers to the specifics of a computer, including the detailed logic design and the packaging technology of the computer. Often a line of computers contains computers with identical instruction set architectures and very similar organizations, but they differ in the detailed hardware implementation. For exam\- ple, the Intel Core i7 (see Chapter 3) and the Intel Xeon E7 (see Chapter 5) are nearly identical but offer different clock rates and different memory systems, mak\- ing the Xeon E7 more effective for server computers.

In this book, the word *architecture* covers all three aspects of computer design—instruction set architecture, organization or microarchitecture, and hardware.

Computer architects must design a computer to meet functional requirements as well as price, power, performance, and availability goals. Figure 1.8 summarizes requirements to consider in designing a new computer. Often, architects also must determine what the functional requirements are, which can be a major task. The requirements may be specific features inspired by the market. Application software typically drives the choice of certain functional requirements by determining how the computer will be used. If a large body of software exists for a particular instruc\- tion set architecture, the architect may decide that a new computer should imple\- ment an existing instruction set. The presence of a large market for a particular class of applications might encourage the designers to incorporate requirements that would make the computer competitive in that market. Later chapters examine many of these requirements and features in depth.

---

<!-- page 23 -->

18 $\square$ Chapter One Fundamentals of Quantitative Design and Analysis

| Functional requirements | Typical features required or supported |
| :--- | :--- |
| **Target of computer** | |
| Application area | Real-time performance for a range of tasks, including interactive performance for graphics, video, and audio; energy efficiency (Chapters 2–5 and 7; Appendix A) |
| Personal mobile device | Balanced performance for a range of tasks, including interactive performance for graphics, video, and audio (Chapters 2–5; Appendix A) |
| General-purpose desktop | Support for databases and transaction processing; enhancements for reliability and availability; support for scalability (Chapters 2, 5, and 7; Appendices A, D, and F) |
| Servers | Throughput performance for many independent tasks; error correction for memory; energy proportionality (Chapters 2, 6, and 7; Appendix F) |
| Clusters/warehouse-scale computers | Often requires special support for graphics or video (or other application-specific extension); power limitations and power control may be required; real-time constraints (Chapters 2, 3, 5, and 7; Appendices A and E) |
| Internet of things/embedded computing | |
| **Level of software compatibility** | Determines amount of existing software for computer |
| At programming language | Most flexible for designer; need new compiler (Chapters 3, 5, and 7; Appendix A) |
| Object code or binary compatible | Instruction set architecture is completely defined—little flexibility—but no investment needed in software or porting programs (Appendix A) |
| **Operating system requirements** | Necessary features to support chosen OS (Chapter 2; Appendix B) |
| Size of address space | Very important feature (Chapter 2); may limit applications |
| Memory management | Required for modern OS; may be paged or segmented (Chapter 2) |
| Protection | Different OS and application needs: page versus segment; virtual machines (Chapter 2) |
| Standards | Certain standards maybe be required by marketplace |
| Floating point | Format and arithmetic: IEEE 754 standard (Appendix J), special arithmetic for graphics or signal processing |
| **I/O interfaces** | For I/O devices: Serial ATA, Serial Attached SCSI, PCI Express (Appendices D and F) |
| Operating systems | UNIX, Windows, Linux, CISCO IOS |
| Networks | Support required for different networks: Ethernet, Infiniband (Appendix F) |
| Programming languages | Languages (ANSI C, C++, Java, Fortran) affect instruction set (Appendix A) |

Figure 1.8 Summary of some of the most important functional requirements an architect faces. The left-hand column describes the class of requirement, while the right-hand column gives specific examples. The right-hand column also contains references to chapters and appendices that deal with the specific issues.

Architects must also be aware of important trends in both the technology and the use of computers because such trends affect not only the future cost but also the longevity of an architecture.

1.4 Trends in Technology

If an instruction set architecture is to prevail, it must be designed to survive rapid changes in computer technology. After all, a successful new instruction set

---

<!-- page 24 -->

## 1.4 Trends in Technology 19

architecture may last decades—for example, the core of the IBM mainframe has been in use for more than 50 years. An architect must plan for technology changes that can increase the lifetime of a successful computer.

To plan for the evolution of a computer, the designer must be aware of rapid changes in implementation technology. Five implementation technologies, which change at a dramatic pace, are critical to modern implementations:

*   **Integrated circuit logic technology**—Historically, transistor density increased by about $35\%$ per year, quadrupling somewhat over four years. Increases in die size are less predictable and slower, ranging from $10\%$ to $20\%$ per year. The combined effect was a traditional growth rate in transistor count on a chip of about $40\%-55\%$ per year, or doubling every $18-24$ months. This trend is popularly known as Moore's Law. Device speed scales more slowly, as we discuss below. Shockingly, Moore's Law is no more. The number of devices per chip is still increasing, but at a decelerating rate. Unlike in the Moore's Law era, we expect the doubling time to be stretched with each new technology generation.

*   **Semiconductor DRAM (dynamic random-access memory)**—This technology is the foundation of main memory, and we discuss it in **Chapter 2**. The growth of DRAM has slowed dramatically, from quadrupling every three years as in the past. The 8-gigabit DRAM was shipping in 2014, but the 16-gigabit DRAM won't reach that state until 2019, and it looks like there will be no 32-gigabit DRAM ($\text{Kim}, 2005$). **Chapter 2** mentions several other technologies that may replace DRAM when it hits its capacity wall.

*   **Semiconductor Flash (electrically erasable programmable read-only memory)**—This nonvolatile semiconductor memory is the standard storage device in PMDs, and its rapidly increasing popularity has fueled its rapid growth rate in capacity. In recent years, the capacity per Flash chip increased by about $50\%-60\%$ per year, doubling roughly every 2 years. Currently, Flash memory is $8 - 10$ times cheaper per bit than DRAM. **Chapter 2** describes Flash memory.

*   **Magnetic disk technology**—Prior to 1990, density increased by about $30\%$ per year, doubling in three years. It rose to $60\%$ per year thereafter, and increased to $100\%$ per year in 1996. Between 2004 and 2011, it dropped back to about $40\%$ per year, or doubled every two years. Recently, disk improvement has slowed to less than $5\%$ per year. One way to increase disk capacity is to add more platters at the same areal density, but there are already seven platters within the one-inch depth of the 3.5-inch form factor disks. There is room for at most one or two more platters. The last hope for real density increase is to use a small laser on each disk read-write head to heat a $30 \text{ nm}$ spot to $400^\circ \text{C}$ so that it can be written magnetically before it cools. It is unclear whether Heat Assisted Magnetic Recording can be manufactured economically and reliably, although Seagate announced plans to ship HAMR in limited production in 2018. HAMR is the last chance for continued improvement in areal density of hard disk

---

<!-- page 25 -->

20 $\quad$ Chapter One Fundamentals of Quantitative Design and Analysis

drives, which are now $8-10$ times cheaper per bit than Flash and $200-300$ times cheaper per bit than DRAM. This technology is central to server- and warehouse-scale storage, and we discuss the trends in detail in Appendix D.
- **Network technology**—Network performance depends both on the performance of switches and on the performance of the transmission system. We discuss the trends in networking in Appendix F.

These rapidly changing technologies shape the design of a computer that, with speed and technology enhancements, may have a lifetime of $3-5$ years. Key tech- nologies such as Flash change sufficiently that the designer must plan for these changes. Indeed, designers often design for the next technology, knowing that when a product begins shipping in volume, the following technology may be the most cost-effective or may have performance advantages. Traditionally, cost has decreased at about the rate at which density increases.

Although technology improves continuously, the impact of these increases can be in discrete leaps, as a threshold that allows a new capability is reached. For example, when MOS technology reached a point in the early $1980$s where between $25,000$ and $50,000$ transistors could fit on a single chip, it became possible to build a single-chip, $32$-bit microprocessor. By the late $1980$s, first-level caches could go on a chip. By eliminating chip crossings within the processor and between the pro- cessor and the cache, a dramatic improvement in cost-performance and energy- performance was possible. This design was simply unfeasible until the technology reached a certain point. With multicore microprocessors and increasing numbers of cores each generation, even server computers are increasingly headed toward a sin- gle chip for all processors. Such technology thresholds are not rare and have a sig- nificant impact on a wide variety of design decisions.

### Performance Trends: Bandwidth Over Latency

As we shall see in Section $1.8$, *bandwidth* or *throughput* is the total amount of work done in a given time, such as megabytes per second for a disk transfer. In contrast, *latency* or *response time* is the time between the start and the completion of an event, such as milliseconds for a disk access. Figure $1.9$ plots the relative improve- ment in bandwidth and latency for technology milestones for microprocessors, memory, networks, and disks. Figure $1.10$ describes the examples and milestones in more detail.

Performance is the primary differentiator for microprocessors and networks, so they have seen the greatest gains: $32,000-40,000 \times$ in bandwidth and $50-90 \times$ in latency. Capacity is generally more important than performance for memory and disks, so capacity has improved more, yet bandwidth advances of $400-2,400 \times$ are still much greater than gains in latency of $8-9 \times$.

Clearly, bandwidth has outpaced latency across these technologies and will likely continue to do so. A simple rule of thumb is that bandwidth grows by at least the square of the improvement in latency. Computer designers should plan accordingly.

---

<!-- page 26 -->

```markdown
1.4 Trends in Technology $\square$ 21

[FIGURE: Log-log plot showing relative bandwidth improvement (Y-axis, logarithmic scale from 1 to 100,000) versus relative latency improvement (X-axis, logarithmic scale from 1 to 100) for Network, Microprocessor, Memory, Disk, and a diagonal line where Latency improvement = Bandwidth improvement.]

**Figure 1.9** Log–log plot of bandwidth and latency milestones in Figure 1.10 relative to the first milestone. Note that latency improved $8-91\times$, while bandwidth improved about $400-32,000\times$. Except for networking, we note that there were modest improvements in latency and bandwidth in the other three technologies in the six years since the last edition: $0\%-23\%$ in latency and $23\%-70\%$ in bandwidth. Updated from Patterson, D., 2004. Latency lags bandwidth. Commun. ACM 47 (10), 71–75.

## Scaling of Transistor Performance and Wires

Integrated circuit processes are characterized by the *feature size*, which is the minimum size of a transistor or a wire in either the $x$ or $y$ dimension. Feature sizes decreased from $10 \mu\text{m}$ in 1971 to $0.016 \mu\text{m}$ in 2017; in fact, we have switched units so production in 2017 is referred to as “$16 \text{ nm}$,” and $7 \text{ nm}$ chips are under way. Since the transistor count per square millimeter of silicon is determined by the surface area of a transistor, the density of transistors increases quadratically with a linear decrease in feature size.
```

---

<!-- page 27 -->

| Microprocessor | 16-Bit address/ bus, microcoded | 32-Bit address/ bus, microcoded | 5-Stage pipeline, on-chip I & D cache, FPU | 2-Way superscalar, 64-bit bus | Out-of-order execution, 3-way superscalar | Out-of-order, on-chip L2 cache | Multicore OOO, 4-way on chip L3 cache, Turbo |
|---|---|---|---|---|---|---|---|
| Product | Intel 80286 | Intel 80386 | Intel Pentium | Intel Pentium Pro | Intel Pentium 4 | Intel Core i7 |
| Year | 1982 | 1985 | 1989 | 1993 | 1997 | 2001 | 2015 |
| Die size ($\text{mm}^2$) | 47 | 43 | 81 | 90 | 308 | 217 | 122 |
| Transistors | 134,000 | 275,000 | 1,200,000 | 3,100,000 | 5,500,000 | 42,000,000 | 1,750,000,000 |
| Processors/chip | 1 | 1 | 1 | 1 | 1 | 1 | 4 |
| Pins | 68 | 132 | 168 | 273 | 387 | 423 | 1400 |
| Latency (clocks) | 6 | 5 | 5 | 5 | 10 | 22 | 14 |
| Bus width (bits) | 16 | 32 | 32 | 64 | 64 | 64 | 196 |
| Clock rate (MHz) | 12.5 | 16 | 25 | 66 | 200 | 1500 | 4000 |
| Bandwidth (MIPS) | 2 | 6 | 25 | 132 | 600 | 4500 | 60,000 |
| Latency (ns) | 320 | 313 | 200 | 76 | 50 | 15 | 4 |
| **Memory module** | DRAM | Page mode DRAM | Fast page mode DRAM | Fast page mode DRAM | Synchronous DRAM | Double data rate SDRAM | DDR4 SDRAM |
| Module width (bits) | 16 | 16 | 16 | 32 | 64 | 64 | 64 |
| Year | 1980 | 1983 | 1986 | 1993 | 1997 | 2000 | 2016 |
| Mbits/DRAM chip | 0.06 | 0.25 | 1 | 16 | 64 | 256 | 4096 |
| Die size ($\text{mm}^2$) | 35 | 45 | 70 | 130 | 170 | 204 | 50 |
| Pins/DRAM chip | 16 | 16 | 18 | 20 | 54 | 66 | 134 |
| Bandwidth (Mbytes/s) | 13 | 40 | 160 | 267 | 640 | 1600 | 27,000 |
| Latency (ns) | 225 | 170 | 125 | 75 | 62 | 52 | 30 |
| Local area network | Ethernet | Fast Ethernet | Gigabit Ethernet | 10 Gigabit Ethernet | 100 Gigabit Ethernet | 400 Gigabit Ethernet |
| IEEE standard | 802.3 | 802.3u | 802.3ab | 802.3ac | 802.3ba | 802.3bs |
| Year | 1978 | 1995 | 1999 | 2003 | 2010 | 2017 |
| Bandwidth (Mbits/seconds) | 10 | 100 | 1000 | 10,000 | 100,000 | 400,000 |
| Latency ($\mu$s) | 3000 | 300 | 340 | 190 | 100 | 60 |
| **Hard disk** | 3600 RPM | 5400 RPM | 7200 RPM | 10,000 RPM | 15,000 RPM | 15,000 RPM |
| Product | CDC Wren 94145-36 | Seagate ST41600 | Seagate ST15150 | Seagate ST39102 | Seagate ST373453 | Seagate ST600MX0062 |
| Year | 1983 | 1990 | 1994 | 1998 | 2003 | 2016 |
| Capacity (GB) | 0.03 | 1.4 | 4.3 | 9.1 | 73.4 | 600 |
| Disk form factor | 5.25 in. | 5.25 in. | 3.5 in. | 3.5 in. | 3.5 in. | 3.5 in. |
| Media diameter | 5.25 in. | 5.25 in. | 3.5 in. | 3.0 in. | 2.5 in. | 2.5 in. |
| Interface | ST-412 | SCSI | SCSI | SCSI | SCSI | SAS |
| Bandwidth (MBytes/s) | 0.6 | 4 | 9 | 24 | 86 | 250 |
| Latency (ms) | 48.3 | 17.1 | 12.7 | 8.8 | 5.7 | 3.6 |

**Figure 1.10** Performance milestones over 25–40 years for microprocessors, memory, networks, and disks. The microprocessor milestones are several generations of IA-32 processors, going from a 16-bit bus, microcoded 80286 to a 64-bit bus, multicore, out-of-order execution, superpipelined Core i7. Memory module milestones go from 16-bit-wide, plain DRAM to 64-bit-wide double data rate version 3 synchronous DRAM. Ethernet advanced from 10 Mbits/s to 400 Gbits/s. Disk milestones are based on rotation speed, improving from 3600 to 15,000 RPM. Each case is best-case bandwidth, and latency is the time for a simple operation assuming no contention. Updated from Patterson, D., 2004. Latency lags bandwidth. Commun. ACM 47 (10), 71–75.

---

<!-- page 28 -->

```markdown
## 1.5 Trends in Power and Energy in Integrated Circuits 23

The increase in transistor performance, however, is more complex. As feature sizes shrink, devices shrink quadratically in the horizontal dimension and also shrink in the vertical dimension. The shrink in the vertical dimension requires a reduction in operating voltage to maintain correct operation and reliability of the transistors. This combination of scaling factors leads to a complex interrelationship between transistor performance and process feature size. To a first approximation, in the past the transistor performance improved linearly with decreasing feature size.

The fact that transistor count improves quadratically with a linear increase in transistor performance is both the challenge and the opportunity for which computer architects were created! In the early days of microprocessors, the higher rate of improvement in density was used to move quickly from 4-bit, to 8-bit, to 16-bit, to 32-bit, to 64-bit microprocessors. More recently, density improvements have supported the introduction of multiple processors per chip, wider SIMD units, and many of the innovations in speculative execution and caches found in Chapters 2–5.

Although transistors generally improve in performance with decreased feature size, wires in an integrated circuit do not. In particular, the signal delay for a wire increases in proportion to the product of its resistance and capacitance. Of course, as feature size shrinks, wires get shorter, but the resistance and capacitance per unit length get worse. This relationship is complex, since both resistance and capacitance depend on detailed aspects of the process, the geometry of a wire, the loading on a wire, and even the adjacency to other structures. There are occasional process enhancements, such as the introduction of copper, which provide one-time improvements in wire delay.

In general, however, wire delay scales poorly compared to transistor performance, creating additional challenges for the designer. In addition to the power dissipation limit, wire delay has become a major design obstacle for large integrated circuits and is often more critical than transistor switching delay. Larger and larger fractions of the clock cycle have been consumed by the propagation delay of signals on wires, but power now plays an even greater role than wire delay.

**1.5 Trends in Power and Energy in Integrated Circuits**

Today, energy is the biggest challenge facing the computer designer for nearly every class of computer. First, power must be brought in and distributed around the chip, and modern microprocessors use hundreds of pins and multiple interconnection layers just for power and ground. Second, power is dissipated as heat and must be removed.

### Power and Energy: A Systems Perspective

How should a system architect or a user think about performance, power, and energy? From the viewpoint of a system designer, there are three primary concerns.

First, what is the maximum power a processor ever requires? Meeting this demand can be important to ensuring correct operation. For example, if a processor
```

---

<!-- page 29 -->

<div line="24">
24 $\quad$ Chapter One Fundamentals of Quantitative Design and Analysis
</div>

attempts to draw more power than a power-supply system can provide (by drawing
more current than the system can supply), the result is typically a voltage drop,
which can cause devices to malfunction. Modern processors can vary widely in
power consumption with high peak currents; hence they provide voltage indexing
methods that allow the processor to slow down and regulate voltage within a wider
margin. Obviously, doing so decreases performance.

Second, what is the sustained power consumption? This metric is widely called
the *thermal design power* (TDP) because it determines the cooling requirement.
TDP is neither peak power, which is often $1.5$ times higher, nor is it the actual aver-
age power that will be consumed during a given computation, which is likely to be
lower still. A typical power supply for a system is typically sized to exceed the
TDP, and a cooling system is usually designed to match or exceed TDP. Failure
to provide adequate cooling will allow the junction temperature in the processor to
exceed its maximum value, resulting in device failure and possibly permanent
damage. Modern processors provide two features to assist in managing heat, since
the highest power (and hence heat and temperature rise) can exceed the long-term
average specified by the TDP. First, as the thermal temperature approaches the
junction temperature limit, circuitry lowers the clock rate, thereby reducing power.
Should this technique not be successful, a second thermal overload trap is activated
to power down the chip.

The third factor that designers and users need to consider is energy and energy
efficiency. Recall that power is simply energy per unit time: $1\ \text{watt} = 1\ \text{joule per}$
second. Which metric is the right one for comparing processors: energy or power?
In general, energy is always a better metric because it is tied to a specific task and
the time required for that task. In particular, the energy to complete a workload is
equal to the average power times the execution time for the workload.

Thus, if we want to know which of two processors is more efficient for a given
task, we need to compare energy consumption (not power) for executing the task.
For example, processor $A$ may have a $20\%$ higher average power consumption
than processor $B$, but if $A$ executes the task in only $70\%$ of the time needed by
$B$, its energy consumption will be $1.2 \times 0.7 = 0.84$, which is clearly better.

One might argue that in a large server or cloud, it is sufficient to consider the
average power, since the workload is often assumed to be infinite, but this is mis-
leading. If our cloud were populated with processor $B$s rather than $A$s, then the
cloud would do less work for the same amount of energy expended. Using energy
to compare the alternatives avoids this pitfall. Whenever we have a fixed workload,
whether for a warehouse-size cloud or a smartphone, comparing energy will be the
right way to compare computer alternatives, because the electricity bill for the
cloud and the battery lifetime for the smartphone are both determined by the energy
consumed.

When is power consumption a useful measure? The primary legitimate use is as
a constraint: for example, an air-cooled chip might be limited to $100\ \text{W}$. It can be
used as a metric if the workload is fixed, but then it's just a variation of the true
metric of energy per task.

---

<!-- page 30 -->

### 1.5 Trends in Power and Energy in Integrated Circuits 25

## Energy and Power Within a Microprocessor

For CMOS chips, the traditional primary energy consumption has been in switching transistors, also called *dynamic energy*. The energy required per transistor is proportional to the product of the capacitive load driven by the transistor and the square of the voltage:

$$
\text{Energy}_{\text{dynamic}} \propto \text{Capacitive load} \times \text{Voltage}^2
$$

This equation is the energy of pulse of the logic transition of $0 \rightarrow 1 \rightarrow 0$ or $1 \rightarrow 0 \rightarrow 1$. The energy of a single transition ($0 \rightarrow 1$ or $1 \rightarrow 0$) is then:

$$
\text{Energy}_{\text{dynamic}} \propto \frac{1}{2} \times \text{Capacitive load} \times \text{Voltage}^2
$$

The power required per transistor is just the product of the energy of a transition multiplied by the frequency of transitions:
$$
\text{Power}_{\text{dynamic}} \propto \frac{1}{2} \times \text{Capacitive load} \times \text{Voltage}^2 \times \text{Frequency switched}
$$

For a fixed task, slowing clock rate reduces power, but not energy. Clearly, dynamic power and energy are greatly reduced by lowering the voltage, so voltages have dropped from $5\text{ V}$ to just under $1\text{ V}$ in 20 years. The capacitive load is a function of the number of transistors connected to an output and the technology, which determines the capacitance of the wires and the transistors.

**Example** Some microprocessors today are designed to have adjustable voltage, so a $15\%$ reduction in voltage may result in a $15\%$ reduction in frequency. What would be the impact on dynamic energy and on dynamic power?

**Answer** Because the capacitance is unchanged, the answer for energy is the ratio of the voltages

$$
\frac{{\text{Energy}_{\text{new}}}}{{\text{Energy}_{\text{old}}}} = \frac{(\text{Voltage} \times 0.85)^2}{{\text{Voltage}^2}} = 0.85^2 = 0.72
$$

which reduces energy to about $72\%$ of the original. For power, we add the ratio of the frequencies

$$
\frac{\text{Power}_{\text{new}}}{\text{Power}_{\text{old}}} = 0.72 \times \frac{(\text{Frequency switched} \times 0.85)}{\text{Frequency switched}} = 0.61
$$

shrinking power to about $61\%$ of the original.

As we move from one process to the next, the increase in the number of transistors switching and the frequency with which they change dominate the decrease in load capacitance and voltage, leading to an overall growth in power consumption and energy. The first microprocessors consumed less than a watt, and the first

---

<!-- page 31 -->

# Chapter One Fundamentals of Quantitative Design and Analysis

32-bit microprocessors (such as the Intel 80386) used about $2\text{ W}$, whereas a $4.0\text{ GHz}$ Intel Core i7-6700K consumes $95\text{ W}$. Given that this heat must be dissipated from a chip that is about $1.5\text{ cm}$ on a side, we are near the limit of what can be cooled by air, and this is where we have been stuck for nearly a decade.

Given the preceding equation, you would expect clock frequency growth to slow down if we can't reduce voltage or increase power per chip. **Figure 1.11** shows that this has indeed been the case since $2003$, even for the microprocessors in **Figure 1.1** that were the highest performers each year. Note that this period of flatter clock rates corresponds to the period of slow performance improvement range in **Figure 1.1**.

Distributing the power, removing the heat, and preventing hot spots have become increasingly difficult challenges. Energy is now the major constraint to using transistors; in the past, it was the raw silicon area. Therefore modern

[FIGURE: A semi-log plot showing the growth in clock rate (in MHz) for various microprocessors from 1978 to 2018. The plot shows an initial rapid growth (labeled 15%/year between 1978 and 1988, and 40%/year between 1988 and 2003), followed by a period of much slower growth (labeled 2%/year after 2003).]

**Figure 1.11** Growth in clock rate of microprocessors in **Figure 1.1**. Between $1978$ and $1986$, the clock rate improved by less than $15\%$ per year while performance improved by $22\%$ per year. During the “renaissance period” of $52\%$ performance improvement per year between $1986$ and $2003$, clock rates shot up almost $40\%$ per year. Since then, the clock rate has been nearly flat, growing at less than $2\%$ per year, while single processor performance improved recently at just $3.5\%$ per year.

---

<!-- page 32 -->

## 1.5 Trends in Power and Energy in Integrated Circuits $\square$ 27

microprocessors offer many techniques to try to improve energy efficiency despite flat clock rates and constant supply voltages:

1. **Do nothing well.** Most microprocessors today turn off the clock of inactive modules to save energy and dynamic power. For example, if no floating-point instructions are executing, the clock to the floating-point unit is disabled. If some cores are idle, their clocks are stopped.

2. **Dynamic voltage-frequency scaling (DVFS).** The second technique comes directly from the preceding formulas. PMDs, laptops, and even servers have periods of low activity where there is no need to operate at the highest clock frequencies and voltages. Modern microprocessors typically offer a few clock frequencies and voltages in which to operate that use lower power and energy. Figure 1.12 plots the potential power savings via DVFS for a server as the workload shrinks for three different clock rates: $2.4$, $1.8$, and $1\ \text{GHz}$. The overall server power savings is about $10\%-15\%$ for each of the two steps.

3. **Design for the typical case.** Given that PMDs and laptops are often idle, memory and storage offer low power modes to save energy. For example, DRAMs have a series of increasingly lower power modes to extend battery life in PMDs and laptops, and there have been proposals for disks that have a mode that spins more slowly when unused to save power. However, you cannot access DRAMs or disks in these modes, so you must return to fully active mode to read or write, no matter how low the access rate. As mentioned, microprocessors for PCs have been designed instead for heavy use at high operating temperatures, relying on on-chip temperature sensors to detect when activity should be reduced automatically to avoid overheating. This “emergency slowdown” allows manufacturers to design for a more typical case and then rely on this safety mechanism if someone really does run programs that consume much more power than is typical.

[FIGURE: A line graph showing Power (% of peak) on the y-axis versus Compute load (%) on the x-axis. Three curves show power consumption for clock rates of $2.4\ \text{GHz}$, $1.8\ \text{GHz}$, and $1\ \text{GHz}$ as compute load varies from Idle to $100\%$. A fourth line segment at the bottom tracks DVS savings (\%) over the compute load.]

**Figure 1.12** Energy savings for a server using an AMD Opteron microprocessor, 8 GB of DRAM, and one ATA disk. At $1.8\ \text{GHz}$, the server can handle at most up to two-thirds of the workload without causing service-level violations, and at $1\ \text{GHz}$, it can safely handle only one-third of the workload (Figure 5.11 in Barroso and Hölzle, 2009).

---

<!-- page 33 -->

28 $\square$ Chapter One Fundamentals of Quantitative Design and Analysis

4. Overclocking. Intel started offering Turbo mode in 2008, where the chip decides that it is safe to run at a higher clock rate for a short time, possibly on just a few cores, until temperature starts to rise. For example, the 3.3 GHz Core i7 can run in short bursts for 3.6 GHz. Indeed, the highest-performing microprocessors each year since 2008 shown in Figure 1.1 have all offered temporary overclocking of about 10% over the nominal clock rate. For single-threaded code, these microprocessors can turn off all cores but one and run it faster. Note that, although the operating system can turn off Turbo mode, there is no notification once it is enabled, so the programmers may be surprised to see their programs vary in performance because of room temperature!

Although dynamic power is traditionally thought of as the primary source of power dissipation in CMOS, static power is becoming an important issue because leakage current flows even when a transistor is off:
$$\text{Power}_{\text{static}} \propto \text{Current}_{\text{static}} \times \text{Voltage}$$

That is, static power is proportional to the number of devices. Thus increasing the number of transistors increases power even if they are idle, and current leakage increases in processors with smaller transistor sizes. As a result, very low-power systems are even turning off the power supply ($\textit{power gating}$) to inactive modules in order to control loss because of leakage. In 2011 the goal for leakage was $25\%$ of the total power consumption, with leakage in high-performance designs sometimes far exceeding that goal. Leakage can be as high as $50\%$ for such chips, in part because of the large SRAM caches that need power to maintain the storage values. (The S in SRAM is for static.) The only hope to stop leakage is to turn off power to the chips’ subsets. Finally, because the processor is just a portion of the whole energy cost of a sys- tem, it can make sense to use a faster, less energy-efficient processor to do the rest of the system to go into a sleep mode. This strategy is known as $\text{race-to-halt}$.

The importance of power and energy has increased the scrutiny on the effi- ciency of an innovation, so the primary evaluation now is tasks per joule or per- formance per watt, contrary to performance per $\text{mm}^2$ of silicon as in the past. This new metric affects approaches to parallelism, as we will see in Chapters 4 and 5.

### The Shift in Computer Architecture Because of Limits of Energy

As transistor improvement decelerates, computer architects must look elsewhere for improved energy efficiency. Indeed, given the energy budget, it is easy today to design a microprocessor with so many transistors that they cannot all be turned on at the same time. This phenomenon has been called $\textit{dark silicon}$, in that much of a chip cannot be unused ($\text{"dark"}$) at any moment in time because of thermal con- straints. This observation has led architects to reexamine the fundamentals of pro- cessors' design in the search for a greater energy-cost performance. Figure 1.13, which lists the energy cost and area cost of the building blocks of a modern computer, reveals surprisingly large ratios. For example, a 32-bit

---

<!-- page 34 -->

## 1.6 Trends in Cost

| Operation: | Energy ($\mu$J) | Relative energy cost | Area ($\mu$m$^2$) | Relative area cost |
| :--- | :---: | :---: | :---: | :---: |
| 8b Add | 0.03 | $\text{ }0\text{ } \text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000\text{ } \text{ }10000$ | 36 | $\text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000$ |
| 16b Add | 0.05 | $\text{ }0\text{ } \text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000\text{ } \text{ }10000$ | 67 | $\text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000$ |
| 32b Add | 0.1 | $\text{ }0\text{ } \text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000\text{ } \text{ }10000$ | 137 | $\text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000$ |
| 16b FB Add | 0.4 | $\text{ }0\text{ } \text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000\text{ } \text{ }10000$ | 1360 | $\text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000$ |
| 32b FB Add | 0.9 | $\text{ }0\text{ } \text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000\text{ } \text{ }10000$ | 4184 | $\text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000$ |
| 8b Mult | 0.2 | $\text{ }0\text{ } \text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000\text{ } \text{ }10000$ | 282 | $\text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000$ |
| 32b Mult | 3.1 | $\text{ }0\text{ } \text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000\text{ } \text{ }10000$ | 3495 | $\text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000$ |
| 16b FB Mult | 1.1 | $\text{ }0\text{ } \text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000\text{ } \text{ }10000$ | 1640 | $\text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000$ |
| 32b FB Mult | 3.7 | $\text{ }0\text{ } \text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000\text{ } \text{ }10000$ | 7700 | $\text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000$ |
| 32b SRAM Read (8KB) | 5 | $\text{ }0\text{ } \text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000\text{ } \text{ }10000$ | N/A | $\text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000$ |
| 32b DRAM Read | 640 | $\text{ }0\text{ } \text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000\text{ } \text{ }10000$ | N/A | $\text{ }1\text{ } \text{ }10\text{ } \text{ }100\text{ } \text{ }1000$ |

Energy numbers are from Mark Horowitz "Computing's Energy problem (and what we can do about it)", ISSCC 2014
Area numbers are from synthesized result using Design compiler under TSMC 45nm tech node. FP units used DesignWare Library.

**Figure 1.13 Comparison of the energy and die area of arithmetic operations and energy cost of accesses to SRAM and DRAM. [Azizi][Dally]. Area is for TSMC 45 nm technology node.**

Floating-point addition uses 30 times as much energy as an 8-bit integer add. The area difference is even larger, by 60 times. However, the biggest difference is in memory: a 32-bit DRAM access takes 20,000 times as much energy as an 8-bit addition. A small SRAM is 125 times more energy-efficient than DRAM, which demonstrates the importance of careful uses of caches and memory buffers.

The new design principle of minimizing energy per task combined with the relative energy and area costs in Figure 1.13 have inspired a new direction for computer architecture, which we describe in Chapter 7. Domain-specific processors save energy by reducing wide floating-point operations and deploying special-purpose memories to reduce accesses to DRAM. They use those savings to provide 10–100 more (narrower) integer arithmetic units than a traditional processor. Although such processors perform only a limited set of tasks, they perform them remarkably faster and more energy efficiently than a general-purpose processor.

Like a hospital with general practitioners and medical specialists, computers in this energy-aware world will likely be combinations of general-purpose cores that can perform any task and special-purpose cores that do a few things extremely well and even more cheaply.

## 1.6 Trends in Cost

Although costs tend to be less important in some computer designs—specifically supercomputers—cost-sensitive designs are of growing significance. Indeed, in the past 35 years, the use of technology improvements to lower cost, as well as increase performance, has been a major theme in the computer industry.

---

<!-- page 35 -->

# Chapter One Fundamentals of Quantitative Design and Analysis

Textbooks often ignore the cost half of cost-performance because costs change, thereby dating books, and because the issues are subtle and differ across industry segments. Nevertheless, it's essential for computer architects to have an under-standing of cost and its factors in order to make intelligent decisions about whether a new feature should be included in designs where cost is an issue. (Imagine archi-tects designing skyscrapers without any information on costs of steel beams and concrete!)

This section discusses the major factors that influence the cost of a computer and how these factors are changing over time.

## The Impact of Time, Volume, and Commoditization

The cost of a manufactured computer component decreases over time even without significant improvements in the basic implementation technology. The underlying principle that drives costs down is the *learning curve*—manufacturing costs decrease over time. The learning curve itself is best measured by change in *yield*—the percentage of manufactured devices that survives the testing procedure. Whether it is a chip, a board, or a system, designs that have twice the yield will have half the cost.

Understanding how the learning curve improves yield is critical to projecting costs over a product's life. One example is that the price per megabyte of DRAM has dropped over the long term. Since DRAMs tend to be priced in close relation-ship to cost—except for periods when there is a shortage or an oversupply—price and cost of DRAM track closely.

Microprocessor prices also drop over time, but because they are less standard-ized than DRAMs, the relationship between price and cost is more complex. In a period of significant competition, price tends to track cost closely, although micro-processor vendors probably rarely sell at a loss.

Volume is a second key factor in determining cost. Increasing volumes affect cost in several ways. First, they decrease the time needed to get through the learn-ing curve, which is partly proportional to the number of systems (or chips) man-ufactured. Second, volume decreases cost because it increases purchasing and manufacturing efficiency. As a rule of thumb, some designers have estimated that costs decrease about $10\%$ for each doubling of volume. Moreover, volume decreases the amount of development costs that must be amortized by each com-puter, thus allowing cost and selling price to be closer and still make a profit.

*Commodities* are products that are sold by multiple vendors in large volumes and are essentially identical. Virtually all the products sold on the shelves of gro-cery stores are commodities, as are standard DRAMs, Flash memory, monitors, and keyboards. In the past 30 years, much of the personal computer industry has become a commodity business focused on building desktop and laptop com-puters running Microsoft Windows.

Because many vendors ship virtually identical products, the market is highly competitive. Of course, this competition decreases the gap between cost and selling

---

<!-- page 36 -->

1.6 Trends in Cost $\blacksquare$ 31

price, but it also decreases cost. Reductions occur because a commodity market has both volume and a clear product definition, which allows multiple suppliers to compete in building components for the commodity product. As a result, the overall product cost is lower because of the competition among the suppliers of the components and the volume efficiencies the suppliers can achieve. This rivalry has led to the low end of the computer business being able to achieve better price-performance than other sectors and has yielded greater growth at the low end, although with very limited profits (as is typical in any commodity business).

## Cost of an Integrated Circuit

Why would a computer architecture book have a section on integrated circuit costs? In an increasingly competitive computer marketplace where standard parts—disks, Flash memory, DRAMs, and so on—are becoming a significant portion of any system's cost, integrated circuit costs are becoming a greater portion of the cost that varies between computers, especially in the high-volume, cost-sensitive portion of the market. Indeed, with PMDs' increasing reliance of whole systems on a chip (SOC), the cost of the integrated circuits is much of the cost of the PMD. Thus computer designers must understand the costs of chips in order to understand the costs of current computers.

Although the costs of integrated circuits have dropped exponentially, the basic process of silicon manufacture is unchanged: A wafer is still tested and chopped into dies that are packaged (see Figures 1.14–1.16). Therefore the cost of a pack-aged integrated circuit is

$$\text{Cost of integrated circuit} = \frac{\text{Cost of die} + \text{Cost of testing die} + \text{Cost of packaging and final test}}{\text{Final test yield}}$$

In this section, we focus on the cost of dies, summarizing the key issues in testing and packaging at the end.

Learning how to predict the number of good chips per wafer requires first learn-ing how many dies fit on a wafer and then learning how to predict the percentage of those that will work. From there it is simple to predict cost:

$$\text{Cost of die} = \frac{\text{Cost of wafer}}{\text{Dies per wafer} \times \text{Die yield}}$$

The most interesting feature of this initial term of the chip cost equation is its sen-sitivity to die size, shown below.

The number of dies per wafer is approximately the area of the wafer divided by the area of the die. It can be more accurately estimated by

$$\text{Dies per wafer} = \frac{\pi \times (\text{Wafer diameter}/2)^2}{\text{Die area}} = \frac{\pi \times \text{Wafer diameter}}{\sqrt{2} \times \text{Die area}}$$

The first term is the ratio of wafer area $(\pi r^2)$ to die area. The second compensates for the "square peg in a round hole" problem—rectangular dies near the periphery

---

<!-- page 37 -->

32 $\square$ Chapter One $*$ Fundamentals of Quantitative Design and Analysis

[FIGURE: Photograph of an Intel Skylake microprocessor die, presumably showing the arrangement of circuits and cores.]

**Figure 1.14** Photograph of an Intel Skylake microprocessor die, which is evaluated in [Chapter 4](link_to_chapter_4).

[FIGURE: A magnified view of a section of the microprocessor die from Figure 1.14, showing blocks labeled "Core" and "Memory Controller," and an annotation indicating "3x Intel® UPI, 3x16 PCIe Gen3, 1x4 DMI$3$".]

**Figure 1.15** The components of the microprocessor die in [Figure 1.14](link_to_figure_1_14) are labeled with their functions.

---

<!-- page 38 -->

1.6 Trends in Cost $\square$ 33

[FIGURE: A photograph of a circular silicon wafer with a grid pattern of integrated circuits visible, and a ruler placed next to it for scale.]

**Figure 1.16** This 200 mm diameter wafer of RISC-V dies was designed by SiFive. It has two types of RISC-V dies using an older, larger processing line. An FE310 die is $2.65 \text{ mm} \times 2.72 \text{ mm}$ and an SiFive test die that is $2.89 \text{ mm} \times 2.72 \text{ mm}$. The wafer contains 1846 of the former and 1866 of the latter, totaling 3712 chips.

of round wafers. Dividing the circumference ($\pi d$) by the diagonal of a square die is approximately the number of dies along the edge.

**Example** Find the number of dies per $300 \text{ mm}$ ($30 \text{ cm}$) wafer for a die that is $1.5 \text{ cm}$ on a side and for a die that is $1.0 \text{ cm}$ on a side.

**Answer** When die area is $2.25 \text{ cm}^2$:
$$
\text{Dies per wafer} = \frac{\pi \times (30/2)^2}{2.25} - \frac{\pi \times 30}{\sqrt{2} \times 2.25} = \frac{706.9}{2.25} - \frac{94.2}{\sqrt{2} \times 2.25} \approx \frac{706.9}{2.25} - \frac{94.2}{2.12} \approx 270
$$
Because the area of the larger die is $2.25$ times bigger, there are roughly $2.25$ as many smaller dies per wafer:
$$
\text{Dies per wafer} = \frac{\pi \times (30/2)^2}{1.00} - \frac{\pi \times 30}{\sqrt{2} \times 1.00} = \frac{706.9}{1.00} - \frac{94.2}{\sqrt{2} \times 1.00} \approx \frac{706.9}{1.00} - \frac{94.2}{1.41} \approx 640
$$

However, this formula gives only the maximum number of dies per wafer. The critical question is: What is the fraction of *good* dies on a wafer, or the *die yield*? A simple model of integrated circuit yield, which assumes that defects are randomly

---

<!-- page 39 -->

34 $\qquad$ Chapter One Fundamentals of Quantitative Design and Analysis

distributed over the wafer and that yield is inversely proportional to the complexity of the fabrication process, leads to the following:

$$\text{Die yield} = \text{Wafer yield} \times 1 / (1 + \text{Defects per unit area} \times \text{Die area})^N$$

This Bose–Einstein formula is an empirical model developed by looking at the yield of many manufacturing lines (Sydow, 2006), and it still applies today. *Wafer yield* accounts for wafers that are completely bad and so need not be tested. For simplicity, we’ll just assume the wafer yield is $100\%$. Defects per unit area is a measure of the random manufacturing defects that occur. In 2017 the value was typically $0.08–0.10$ defects per square inch for a $28-\text{nm}$ node and $0.016-0.030$ for the newer $16\text{ nm}$ node because it depends on the maturity of the process (recall the learning curve mentioned earlier). The metric versions are $0.012-0.016$ defects per square centimeter for $28\text{ nm}$ and $0.0016-0.0047$ for $16\text{ nm}$. Finally, $N$ is a parameter called the process-complexity factor, a measure of manufacturing difficulty. For $28\text{ nm}$ processes in $2017$, $N$ is $7.5-9.5$. For a $16\text{ nm}$ process, $N$ ranges from $10$ to $14$.

**Example** Find the die yield for dies that are $1.5\text{ cm}$ on a side and $1.0\text{ cm}$ on a side, assuming a defect density of $0.047$ per $\text{cm}^2$ and $N$ is $12$.

**Answer** The total die areas are $2.25$ and $1.00\text{ cm}^2$. For the larger die, the yield is
$$\text{Die yield} = 1/(1 + 0.047 \times 2.25)^{12} \times 270 \approx 120$$
For the smaller die, the yield is
$$\text{Die yield} = 1/(1 + 0.047 \times 1.00)^{12} \times 640 \approx 444$$
The bottom line is the number of good dies per wafer. Less than half of all the large dies are good, but nearly $70\%$ of the small dies are good.

Although many microprocessors fall between $1.00$ and $2.25\text{ cm}^2$, low-end embedded $32-\text{bit}$ processors are sometimes as small as $0.05\text{ cm}^2$, processors used for embedded control (or inexpensive IoT devices) are often less than $0.01\text{ cm}^2$, and high-end server and GPU chips can be as large as $8\text{ cm}^2$.

Given the tremendous price pressures on commodity products such as DRAM and SRAM, designers have included redundancy as a way to raise yield. For a number of years, DRAMs have regularly included some redundant memory cells so that a certain number of flaws can be accommodated. Designers have used similar techniques in both standard SRAMs and in large SRAM arrays used for caches within microprocessors. GPUs have $4$ redundant processors out of $84$ for the same reason. Obviously, the presence of redundant entries can be used to boost the yield significantly.

---

<!-- page 40 -->

1.6 Trends in Cost $\square$ 35

In 2017 processing of a $300 \text{ mm}$ (12-inch) diameter wafer in a $28 \text{ nm}$ technology costs between $\$4000$ and $\$5000$, and a $16 \text{ nm}$ wafer costs about $\$7000$. Assuming a processed wafer cost of $\$7000$, the cost of the $1.00 \text{ cm}^2$ die would be around $\$16$, but the cost per die of the $2.25 \text{ cm}^2$ die would be about $\$58$, or almost four times the cost of a die that is a little over twice as large.

What should a computer designer remember about chip costs? The manufacturing process dictates the wafer cost, wafer yield, and defects per unit area, so the sole control of the designer is die area. In practice, because the number of defects per unit area is small, the number of good dies per wafer, and therefore the cost per die, grows roughly as the square of the die area. The computer designer affects die size and thus cost, both by what functions are included on or excluded from the die and by the number of I/O pins.

Before we have a part that is ready for use in a computer, the die must be tested (to separate the good dies from the bad), packaged, and tested again after packaging. These steps all add significant costs, increasing the total by half.

The preceding analysis focused on the variable costs of producing a functional die, which is appropriate for high-volume integrated circuits. There is, however, one very important part of the fixed costs that can significantly affect the cost of an integrated circuit for low volumes (less than 1 million parts), namely, the cost of a mask set. Each step in the integrated circuit process requires a separate mask. Therefore, for modern high-density fabrication processes with up to 10 metal layers, mask costs are about $\$4$ million for $16 \text{ nm}$ and $\$1.5$ million for $28 \text{ nm}$.

The good news is that semiconductor companies offer "shuttle runs" to dramatically lower the costs of tiny test chips. They lower costs by putting many small designs onto a single die to amortize the mask costs, and then later split the dies into smaller pieces for each project. Thus TSMC delivers $80 \text{–} 100$ untested dies that are $1.57 \times 1.57 \text{ mm}$ in a $28 \text{ nm}$ process for $\$30,000$ in $2017$. Although these die are tiny, they offer the architect millions of transistors to play with. For example, several RISC-V processors would fit on such a die.

Although shuttle runs help with prototyping and debugging runs, they don't address small-volume production of tens to hundreds of thousands of parts. Because mask costs are likely to continue to increase, some designers are incorporating reconfigurable logic to enhance the flexibility of a part and thus reduce the cost implications of masks.

### Cost Versus Price

With the commoditization of computers, the margin between the cost to manufacture a product and the price the product sells for has been shrinking. Those margins pay for a company's research and development (R\&D), marketing, sales, manufacturing equipment maintenance, building rental, cost of financing, pretax profits, and taxes. Many engineers are surprised to find that most companies spend only $4\%$ (in the commodity PC business) to $12\%$ (in the high-end server business) of their income on R\&D, which includes all engineering.

---

<!-- page 41 -->

# Cost of Manufacturing Versus Cost of Operation

For the first four editions of this book, cost meant the cost to build a computer and price meant price to purchase a computer. With the advent of WSCs, which contain tens of thousands of servers, the cost to operate the computers is significant in addition to the cost of purchase. Economists refer to these two costs as capital expenses (CAPEX) and operational expenses (OPEX).

As Chapter 6 shows, the amortized purchase price of servers and networks is about half of the monthly cost to operate a WSC, assuming a short lifetime of the IT equipment of $3-4$ years. About $40\%$ of the monthly operational costs are for power use and the amortized infrastructure to distribute power and to cool the IT equipment, despite this infrastructure being amortized over $10-15$ years. Thus, to lower operational costs in a WSC, computer architects need to use energy efficiently.

## 1.7 Dependability

Historically, integrated circuits were one of the most reliable components of a computer. Although their pins may be vulnerable, and faults may occur over communication channels, the failure rate inside the chip was very low. That conventional wisdom is changing as we head to feature sizes of $16 \text{ nm}$ and smaller, because both transient faults and permanent faults are becoming more commonplace, so architects must design systems to cope with these challenges. This section gives a quick overview of the issues in dependability, leaving the official definition of the terms and approaches to Section D.3 in Appendix D.

Computers are designed and constructed at different layers of abstraction. We can descend recursively down through a computer seeing components enlarge themselves to full subsystems until we run into individual transistors. Although some faults are widespread, like the loss of power, many can be limited to a single component in a module. Thus utter failure of a module at one level may be considered merely a component error in a higher-level module. This distinction is helpful in trying to find ways to build dependable computers.

One difficult question is deciding when a system is operating properly. This theoretical point became concrete with the popularity of Internet services. Infrastructure providers started offering *service level agreements* (SLAs) or *service level objectives* (SLOs) to guarantee that their networking or power service would be dependable. For example, they would pay the customer a penalty if they did not meet an agreement of some hours per month. Thus an SLA could be used to decide whether the system was up or down.

Systems alternate between two states of service with respect to an SLA:
1. *Service accomplishment*, where the service is delivered as specified.
2. *Service interruption*, where the delivered service is different from the SLA.

---

<!-- page 42 -->

1.7 Dependability $\qquad 37$

Transitions between these two states are caused by failures (from state 1 to state 2) or restorations (2 to 1). Quantifying these transitions leads to the two main measures of dependability:

*   Module reliability is a measure of the continuous service accomplishment (or, equivalently, of the time to failure) from a reference initial instant. Therefore the **mean time to failure (MTTF)** is a reliability measure. The reciprocal of MTTF is a rate of failures, generally reported as failures per billion hours of operation, or **FIT** (*for failures in time*). Thus an MTTF of $1,000,000$ hours equals $10^9/10^6$ or $1000$ FIT. Service interruption is measured as **mean time to repair (MTTR)**. Mean time between failures (MTBF) is simply the sum of MTTF + MTTR. Although MTBF is widely used, MTTF is often the more appropriate term. If a collection of modules has exponentially distributed lifetimes—meaning that the age of a module is not important in probability of failure—the overall failure rate of the collection is the sum of the failure rates of the modules.
*   Module **availability** is a measure of the service accomplishment with respect to the alternation between the two states of accomplishment and interruption. For nonredundant systems with repair, module availability is
    $$\text{Module availability} = \frac{\text{MTTF}}{\text{MTTF} + \text{MTTR}}$$

Note that reliability and availability are now quantifiable metrics, rather than synonyms for dependability. From these definitions, we can estimate reliability of a system quantitatively if we make some assumptions about the reliability of components and that failures are independent.

$$\text{Example} \qquad \text{Assume a disk subsystem with the following components and MTTF:}$$
*   10 disks, each rated at $1,000,000$-hour MTTF
*   1 ATA controller, $500,000$-hour MTTF
*   1 power supply, $200,000$-hour MTTF
*   1 fan, $200,000$-hour MTTF
*   1 ATA cable, $1,000,000$-hour MTTF

Using the simplifying assumptions that the lifetimes are exponentially distributed and that failures are independent, compute the MTTF of the system as a whole.

$$\text{Answer} \qquad \text{The sum of the failure rates is}$$
$$\text{Failure rate}_{\text{system}} = 10 \times \frac{1}{1,000,000} + \frac{1}{500,000} + \frac{1}{200,000} + \frac{1}{200,000} + \frac{1}{1,000,000}$$
$$= \frac{10+2+5+5+1}{1,000,000 \text{ hours}} = \frac{23}{1,000,000} = \frac{23,000}{1,000,000,000 \text{ hours}}$$

---

<!-- page 43 -->

38 $\square$ Chapter One Fundamentals of Quantitative Design and Analysis

or 23,000 FIT. The MTTF for the system is just the inverse of the failure rate
$$ \text{MTTF}_{\text{system}} = \frac{1}{\text{Failure rate}_{\text{system}}} = \frac{1}{1,000,000,000 \text{ hours}} = 43,500 \text{ hours} $$
or just under 5 years.

The primary way to cope with failure is redundancy, either in time (repeat the operation to see if it still is erroneous) or in resources (have other components to take over from the one that failed). Once the component is replaced and the system is fully repaired, the dependability of the system is assumed to be as good as new. Let's quantify the benefits of redundancy with an example.

**Example** Disk subsystems often have redundant power supplies to improve dependability. Using the preceding components and MTTFs, calculate the reliability of redundant power supplies. Assume that one power supply is sufficient to run the disk subsystem and that we are adding one redundant power supply.

**Answer** We need a formula to show what to expect when we can tolerate a failure and still provide service. To simplify the calculations, we assume that the lifetimes of the components are exponentially distributed and that there is no dependency between the component failures. MTTF for our redundant power supplies is the mean time until one power supply fails divided by the chance that the other will fail before the first one is replaced. Thus, if the chance of a second failure before repair is small, then the MTTF of the pair is large.

Since we have two power supplies and independent failures, the mean time until one supply fails is $\text{MTTF}_{\text{power supply}}/2$. A good approximation of the probability of a second failure is $\text{MTTR}/2$ over the mean time until the other power supply fails. Therefore a reasonable approximation for a redundant pair of power supplies is
$$ \text{MTTF}_{\text{power supply pair}} = \frac{\text{MTTF}_{\text{power supply}}/2}{\text{MTTR}_{\text{power supply}}} \frac{\text{MTTF}_{\text{power supply}}^2}{\text{MTTF}_{\text{power supply}}} = \frac{\text{MTTF}_{\text{power supply}}^2}{2 \times \text{MTTR}_{\text{power supply}}} $$

Using the preceding MTTF numbers, if we assume it takes on average 24 hours for a human operator to notice that a power supply has failed and to replace it, the reliability of the fault tolerant pair of power supplies is
$$ \text{MTTF}_{\text{power supply pair}} = \frac{\text{MTTF}_{\text{power supply}}^2}{2 \times \text{MTTR}_{\text{power supply}}} = \frac{200,000^2}{2 \times 24} \approx 830,000,000 $$
making the pair about 4150 times more reliable than a single power supply.

Having quantified the cost, power, and dependability of computer technology, we are ready to quantify performance.

---

<!-- page 44 -->

```markdown
## 1.8 Measuring, Reporting, and Summarizing Performance

When we say one computer is faster than another one is, what do we mean? The user of a cell phone may say a computer is faster when a program runs in less time, while an Amazon.com administrator may say a computer is faster when it completes more transactions per hour. The cell phone user wants to reduce *response time*—the time between the start and the completion of an event—also referred to as *execution time*. The operator of a WSC wants to increase *throughput*—the total amount of work done in a given time.

In comparing design alternatives, we often want to relate the performance of two different computers, say, X and Y. The phrase “X is faster than Y” is used here to mean that the response time or execution time is lower on X than on Y for the given task. In particular, “X is *n* times as fast as Y” will mean

$$\frac{\text{Execution time}_Y}{\text{Execution time}_X} = n$$

Since execution time is the reciprocal of performance, the following relationship holds:

$$n = \frac{\text{Execution time}_Y}{\text{Execution time}_X} = \frac{\frac{1}{\text{Performance}_Y}}{\frac{1}{\text{Performance}_X}} = \frac{\text{Performance}_X}{\text{Performance}_Y}$$

The phrase “the throughput of X is 1.3 times as fast as Y” signifies here that the number of tasks completed per unit time on computer X is 1.3 times the number completed on Y.

Unfortunately, time is not always the metric quoted in comparing the performance of computers. Our position is that the only consistent and reliable measure of performance is the execution time of real programs, and that all proposed alternatives to time as the metric or to real programs as the items measured have eventually led to misleading claims or even mistakes in computer design.

Even execution time can be defined in different ways depending on what we count. The most straightforward definition of time is called *wall-clock time*, *response time*, or *elapsed time*, which is the latency to complete a task, including storage accesses, memory accesses, input/output activities, operating system overhead—everything. With multiprogramming, the processor works on another program while waiting for I/O and may not necessarily minimize the elapsed time of one program. Thus we need a term to consider this activity. *CPU time* recognizes this distinction and means the time the processor is computing, *not* including the time waiting for I/O or running other programs. (Clearly, the response time seen by the user is the elapsed time of the program, not the CPU time.)

Computer users who routinely run the same programs would be the perfect candidates to evaluate a new computer. To evaluate a new system, these users would simply compare the execution time of their *workloads*—the mixture of programs
```

---

<!-- page 45 -->

# Chapter One **Fundamentals of Quantitative Design and Analysis**

and operating system commands that users run on a computer. Few are in this happy situation, however. Most must rely on other methods to evaluate computers, and often after evaluation, hoping that these methods will predict performance for their range of the new computer. One approach is benchmark programs, which are programs that many companies use to establish the relative performance of their computers.

## Benchmarks

The best choice of benchmarks to measure performance is real applications, such as Google Translate mentioned in Section 1.1. Attempts at running programs that are much simpler than a real application have led to performance pitfalls. Examples include
*   *Kernels*, which are small, key pieces of real applications.
*   *Toy programs*, which are 100-line programs from beginning programming assignments, such as Quicksort.
*   *Synthetic benchmarks*, which are fake programs invented to try to match the profile and behavior of real applications, such as Dhrystone.

All three are discredited today, usually because the compiler writer and architect can conspire to make the computer appear faster on these stand-in programs than on real applications. Regrettably for your authors—who dropped the fallacy about using synthetic benchmarks to characterize performance in the fourth edition of this book since we thought all computer architects agreed it was disreputable—the synthetic program Dhrystone is still the most widely quoted benchmark for embedded processors in 2017!

Another issue is the conditions under which the benchmarks are run. One way to improve the performance of a benchmark has been with benchmark-specific compiler flags; these flags often caused transformations that would be illegal on many programs or would slow down performance on others. To restrict this process and increase the significance of the results, benchmark developers typically require the vendor to use one compiler and one set of flags for all the programs in the same language (such as C++ or C). In addition to the question of compiler flags, another question is whether source code modifications are allowed. There are three different approaches to addressing this question:

1.  No source code modifications are allowed.
2.  Source code modifications are allowed but are essentially impossible. For example, database benchmarks rely on standard database programs that are tens of millions of lines of code. The database companies are highly unlikely to make changes to enhance the performance for one particular computer.
3.  Source modifications are allowed, as long as the altered version produces the same output.

---

<!-- page 46 -->

1.8 Measuring, Reporting, and Summarizing Performance $41$

The key issue that benchmark designers face in deciding to allow modification of the source is whether such modifications will reflect real practice and provide useful insight to users, or whether the changes simply reduce the accuracy of the benchmarks as predictors of real performance. As we will see in Chapter 7, domain-specific architects often follow the third option when creating processors for well-defined tasks.

To overcome the danger of placing too many eggs in one basket, collections of benchmark applications, called *benchmark suites*, are a popular measure of performance of processors with a variety of applications. Of course, such collections are only as good as the constituent individual benchmarks. Nonetheless, a key advantage of such suites is that the weakness of any one benchmark is lessened by the presence of the other benchmarks. The goal of a benchmark suite is that it will characterize the real relative performance of two computers, particularly for programs not in the suite that customers are likely to run.

A cautionary example is the Electronic Design News Embedded Microprocessor Benchmark Consortium (or EEMBC, pronounced "embassy") benchmarks. It is a set of 41 kernels used to predict performance of different embedded applications: automotive/industrial, consumer, networking, office automation, and telecommunications. EEMBC reports unmodified performance and "full fury" performance, where almost anything goes. Because these benchmarks use small kernels, and because of the reporting options, EEMBC does not have the reputation of being a good predictor of relative performance of different embedded computers in the field. This lack of success is why Dhrystone, which EEMBC was trying to replace, is sadly still used.

One of the most successful attempts to create standardized benchmark application suites has been the SPEC (Standard Performance Evaluation Corporation), which had its roots in efforts in the late 1980s to deliver better benchmarks for workstations. Just as the computer industry has evolved over time, so has the need for different benchmark suites, and there are now SPEC benchmarks to cover many application classes. All the SPEC benchmark suites and their reported results are found at http://www.spec.org.

Although we focus our discussion on the SPEC benchmarks in many of the following sections, many benchmarks have also been developed for PCs running the Windows operating system.

### Desktop Benchmarks

Desktop benchmarks divide into two broad classes: processor-intensive benchmarks and graphics-intensive benchmarks, although many graphics benchmarks also include intensive processor activity. SPEC originally created a benchmark set focusing on processor performance (initially called SPEC89), which has evolved into its sixth generation: SPEC CPU2017, which follows SPEC2006, SPEC2000, SPEC95, SPEC92, and SPEC89. SPEC CPU2017 consists of a set of 10 integer benchmarks (CINT2017) and 17 floating-point benchmarks (CFP2017). Figure 1.17 describes the current SPEC CPU benchmarks and their ancestry.

---

<!-- page 47 -->

## Chapter One Fundamentals of Quantitative Design and Analysis

[TABLE: Benchmark name by SPEC generation]

| Category / Benchmark | SPEC2017 | SPEC2006 | SPEC2000 | SPEC95 | SPEC92 | SPEC89 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| GNU C compiler | | | | | | gcc |
| Perl interpreter | | perl | | | | espresso |
| Route planning | | | | | | li |
| General data compression | xz | bzip2 | gzip | compress | lz |
| Discrete Event simulation - computer network | | omnetpp | | | | |
| XML to HTML conversion via XSLT | | xalancbmk | | | | |
| Video compression | | h264ref | X264 | m88ksim | | |
| Artificial Intelligence: alpha-beta tree search (Chess) | | sjeng | deepsjcng | ijpeg | go |
| Artificial Intelligence: Monte Carlo tree search (Go) | | gobmk | leela | vortex | vortex |
| Artificial Intelligence: recursive solution generator (Sudoku) | | astar | exchange2 | | | |
| Explosion modeling | | hmmer | | | | |
| Physics: relativity | | libquantum | | | | |
| Molecular dynamics | | cactusBSSN | biwaves | | | |
| Ray tracing | | namd | povray | | | |
| Fluid dynamics | | wrf | lbm | | | |
| Weather forecasting | | gamess | | | | |
| Biomedical imaging: optical tomography with finite elements | | parest | | | | |
| 3D rendering and animation | blender | | | | |
| Atmosphere modeling | milc | zeusmp | | | | |
| Molecular dynamics | cam4 | gromacs | | | | |
| Image manipulation | imagick | leslie3d | | | | |
| Computational Electromagnetics | nab | dealil | | | | |
| Regional ocean modeling | fotonik3d | soplex | | | | |
| | roms | tomt | | | | |
| | | GemsFDTD | Tonto | | | |
| | | sphinx3d | | | | |
| | | sixtrack | | | | |
| | | | parser | crafty | | |
| | | | vpr | | | |
| | | | twolf | | | |
| | | | vortex | | | |
| | | | eon | | | |
| | | | gzip | | | |
| | | | bzip2 | | | |
| | | | mcf | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |

**Figure 1.17 SPEC2017 programs and the evolution of the SPEC benchmarks over time, with integer programs above the line and floating-point programs below the line.** Of the 10 SPEC2017 integer programs, 5 are written in C++, 4 in C, and 1 in Fortran. For the floating-point programs, the split is 3 in Fortran, 2 in C, and 6 in mixed C, C++, and C++. In 2017 releases, Gcc is the senior citizen of the group. Only 3 integer programs and 3 floating-point programs survived 1992, 1995, 2000, 2006, and 2017 releases. Gcc is the senior citizen of the group. All 82 of the programs in the 1989, 3 floating-point programs survived three or more generations. Although a few are carried over from generation to generation, the version of the program changes and either the input or the size of the benchmark is often expanded to increase its running time and to avoid perturbation in measurement or domination of the execution time by some factor other than CPU time. The benchmark descriptions on the left are for SPEC2017 only and do not apply to earlier versions. Programs in the same row from different generations of SPEC are generally not related; for example, fppfp is not a CFD code like biwaves.

---

<!-- page 48 -->

## 1.8 Measuring, Reporting, and Summarizing Performance 43

SPEC benchmarks are real programs modified to be portable and to minimize the effect of I/O on performance. The integer benchmarks vary from part of a C compiler to a go program to a video compression. The floating-point benchmarks include molecular dynamics, ray tracing, and weather forecasting. The SPEC CPU suite is useful for processor benchmarking for both desktop systems and single-processor servers. We will see data on many of these programs throughout this book. However, these programs share little with modern programming languages and environments and the Google Translate application that Section 1.1 describes. Nearly half of them are written at least partially in Fortran! They are even statically linked instead of being dynamically linked like most real programs. Alas, the SPEC2017 applications themselves may be real, but they are not inspiring. It’s not clear that SPECINT2017 and SPECFP2017 capture what is exciting about computing in the 21st century.

In Section 1.11, we describe pitfalls that have occurred in developing the SPEC CPU2017 benchmark suite, as well as the challenges in maintaining a useful and predictive benchmark suite.

SPEC CPU2017 is aimed at processor performance, but SPEC offers many other benchmarks. Figure 1.18 lists the 17 SPEC benchmarks that are active in 2017.

### Server Benchmarks

Just as servers have multiple functions, so are there multiple types of benchmarks. The simplest benchmark is perhaps a processor throughput-oriented benchmark. SPEC CPU2017 uses the SPEC CPU benchmarks to construct a simple throughput benchmark where the processing rate of a multiprocessor can be measured by running multiple copies (usually as many as there are processors) of each SPEC CPU benchmark and converting the CPU time into a rate. This leads to a measurement called the SPECRate, and it is a measure of request-level parallelism from Section 1.2. To measure thread-level parallelism, SPEC offers what they call high-performance computing benchmarks around OpenMP and MPI as well as for accelerators such as GPUs (see Figure 1.18).

- Other than SPECRate, most server applications and benchmarks have significant I/O activity arising from either storage or network traffic, including benchmarks for file server systems, for web servers, and for database and transaction-processing systems. SPEC offers both a file server benchmark (SPEC SFS) and a Java server benchmark. (Appendix D discusses some file and I/O system benchmarks in detail.) SPECvirt\_Sc2013 evaluates end-to-end performance of virtualized data center servers. Another SPEC benchmark measures power, which we examine in Section 1.10.

- Transaction-processing (TP) benchmarks measure the ability of a system to handle transactions that consist of database accesses and updates. Airline reservation systems and bank ATM systems are typical examples of TP; more sophisticated TP systems involve complex databases and decision-making.

---

<!-- page 49 -->

**44 $\quad$ Chapter One Fundamentals of Quantitative Design and Analysis**

| Category | Name | Measures performance of |
| :--- | :--- | :--- |
| Cloud | Cloud\_IaaS 2016 | Cloud using NoSQL database transaction and K-Means clustering using map/reduce |
| CPU | CPU2017 | Compute-intensive integer and floating-point workloads |
| | SPECviewperf$^{\text{R}}$ 12 | 3D graphics in systems running OpenGL and Direct X |
| | SPECwpc V2.0 | Workstations running professional apps under the Windows OS |
| Graphics and workstation performance | SPECacpSm for 3ds Max 2015$^{\text{TM}}$ | 3D graphics running the proprietary Autodesk 3ds Max 2015 app |
| | SPECacpSm for Maya$^{\text{R}}$ 2012 | 3D graphics running the proprietary Autodesk 3ds Max 2012 app |
| | SPECacpSm for PTC Creo 3.0 | 3D graphics running the proprietary PTC Creo 3.0 app |
| | SPECacpSm for Siemens NX 9.0 and 10.0 | 3D graphics running the proprietary Siemens NX 9.0 or 10.0 app |
| | SPECacpSm for SolidWorks 2015 | 3D graphics of systems running the proprietary SolidWorks 2015 CAD/CAM app |
| High performance computing | ACCEL | Accelerator and host CPU running parallel applications using OpenCL and OpenACC |
| | MPI2007 | MPI-parallel, floating-point, compute-intensive programs running on clusters and SMPs |
| | OMP2012 | Parallel apps running OpenMP |
| Java client/server | SPECjbb2015 | Java servers |
| Power | SPECpower\_ssj2008 | Power of volume server class computers running SPECjbb2015 |
| Solution File Server (SFS) | SFS2014 | File server throughput and response time |
| | SPECbfs2008 | File servers utilizing the NFSv3 and CIFS protocols |
| Virtualization | SPECvirt\_sc2013 | Datacenter servers used in virtualized server consolidation |

**Figure 1.18** Active benchmarks from SPEC as of 2017.

In the mid-1980s, a group of concerned engineers formed the vendor-independent Transaction Processing Council (TPC) to try to create realistic and fair benchmarks for TP. The TPC benchmarks are described at http://www.tpc.org. The first TPC benchmark, TPC-A, was published in 1985 and has since been replaced and enhanced by several different benchmarks. TPC-C, initially created in 1992, simulates a complex query environment. TPC-H models ad hoc decision support the queries are unrelated and knowledge of past queries cannot be used to optimize future queries. The TPC-DI benchmark, a new data integration (DI) task also known as ETL, is an important part of data warehousing. TPC-E is an online transaction processing (OLTP) workload that simulates a brokerage firm's customer accounts.

---

<!-- page 50 -->

1.8 Measuring, Reporting, and Summarizing Performance $\square$ 45

Recognizing the controversy between traditional relational databases and "No
SQL" storage solutions, TPCx-HS measures systems using the Hadoop file system
running MapReduce programs, and TPC-DS measures a decision support system
that uses either a relational database or a Hadoop-based system. TPCx-VMS and
TPCx-V measure database performance for virtualized systems, and TPC-Energy
adds energy metrics to all the existing TPC benchmarks.

All the TPC benchmarks measure performance in transactions per second. In
addition, they include a response time requirement so that throughput performance
is measured only when the response time limit is met. To model real-world sys-
tems, higher transaction rates are also associated with larger systems, in terms
of both users and the database to which the transactions are applied. Finally, the
system cost for a benchmark system must be included as well to allow accurate
comparisons of cost-performance. TPC modified its pricing policy so that there
is a single specification for all the TPC benchmarks and to allow verification of
the prices that TPC publishes.

### Reporting Performance Results

The guiding principle of reporting performance measurements should be *repro-
ducibility*—list everything another experimenter would need to duplicate the
results. A SPEC benchmark report requires an extensive description of the com-
puter and the compiler flags, as well as the publication of both the baseline and
the optimized results. In addition to hardware, software, and baseline tuning
parameter descriptions, a SPEC report contains the actual performance times,
shown both in tabular form and as a graph. A TPC benchmark report is even more
complete, because it must include results of a benchmarking audit and cost
information. These reports are excellent sources for finding the real costs of com-
puting systems, since manufacturers compete on high performance and cost-
performance.

### Summarizing Performance Results

In practical computer design, one must evaluate myriad design choices for their
relative quantitative benefits across a suite of benchmarks believed to be relevant.
Likewise, consumers trying to choose a computer will rely on performance mea-
surements from benchmarks, which ideally are similar to the users' applications. In
both cases, it is useful to have measurements for a suite of benchmarks so that the
performance of important applications is similar to that of one or more benchmarks
in the suite and so that variability in performance can be understood. In the best
case, the suite resembles a statistically valid sample of the application space,
but such a sample requires more benchmarks than are typically found in most suites
and requires a randomized sampling, which essentially no benchmark suite uses.

---

<!-- page 51 -->

46 $\square$ Chapter One Fundamentals of Quantitative Design and Analysis

Once we have chosen to measure performance with a benchmark suite, we want to be able to summarize the performance results of the suite in a unique number. A simple approach to computing a summary result would be to compare the arithmetic mean of the execution times of the programs in the suite. An alternative would be to add a weighting factor to each benchmark and use the weighted arithmetic mean as the single number to summarize performance. One approach is to use weights that make all programs execute an equal time on some reference computer, but this biases the results toward the performance characteristics of the reference computer.

Rather than pick weights, we could normalize execution times to a reference computer by dividing the time on the computer being rated by the time on the computer being rated, yielding a ratio proportional to performance. SPEC uses this approach, calling the ratio the SPECratio. It has a particularly useful property that matches the way we benchmark computer performance throughout this text—namely, comparing performance ratios. For example, suppose that the SPECratio of computer A on a benchmark is $1.25$ times as fast as computer B; then we know
$$1.25 = \frac{\text{SPEC Ratio}_{\text{A}}}{\text{SPEC Ratio}_{\text{B}}} = \frac{\frac{\text{Execution time}_{\text{reference}}}{\text{Execution time}_{\text{A}}}}{\frac{\text{Execution time}_{\text{reference}}}{\text{Execution time}_{\text{B}}}} = \frac{\text{Execution time}_{\text{B}}}{\text{Execution time}_{\text{A}}} = \frac{\text{Performance}_{\text{A}}}{\text{Performance}_{\text{B}}}$$

Notice that the execution times on the reference computer drop out and the choice of the reference computer is irrelevant when the comparisons are made as a ratio, which is the approach we consistently use. Figure $1.19$ gives an example.

Because a SPECratio is a ratio rather than an absolute execution time, the mean must be computed using the geometric mean. (Because SPECratios have no units, comparing SPECratios arithmetically is meaningless.) The formula is
$$\text{Geometric mean} = \sqrt[n]{\prod_{i=1}^{n} \text{sample}_{i}}$$
In the case of SPEC, $\text{sample}_{i}$ is the SPECratio for program $i$. Using the geometric mean ensures two important properties:
1. The geometric mean of the ratios is the same as the ratio of the geometric means.
2. The ratio of the geometric means is equal to the geometric mean of the performance ratios, which implies that the choice of the reference computer is irrelevant.

Therefore the motivations to use the geometric mean are substantial, especially when we use performance ratios to make comparisons.

---

<!-- page 52 -->

## 1.8 Measuring, Reporting, and Summarizing Performance $\square$ 47

**Example** Show that the ratio of the geometric means is equal to the geometric mean of the performance ratios and that the reference computer of SPECRatio does not matter.

**Answer** Assume two computers A and B and a set of SPECRatios for each.

$$\frac{\text{Geometric mean}_A}{\text{Geometric mean}_B} = \sqrt[n]{\prod_{i=1}^{n} \text{SPECRatio}_i A} = \sqrt[n]{\prod_{i=1}^{n} \frac{\text{SPECRatio}_i B}{}}$$

$$= \sqrt[n]{\prod_{i=1}^{n} \frac{\text{Execution time}_{i,\text{reference}}}{\text{Execution time}_{i,A}}} = \sqrt[n]{\prod_{i=1}^{n} \frac{\text{Execution time}_{i,B}}{\text{Execution time}_{i,\text{reference}}}} = \sqrt[n]{\prod_{i=1}^{n} \frac{\text{Execution time}_{i,B}}{\text{Execution time}_{i,A}}} = \sqrt[n]{\prod_{i=1}^{n} \frac{\text{Performance}_A i}{\text{Performance}_B i}}$$

That is, the ratio of the geometric means of the SPECRatios of A and B is the geometric mean of the performance ratios of A to B of all the benchmarks in the suite. Figure 1.19 demonstrates this validity using examples from SPEC.

| Benchmarks | Sun Ultra Enterprise 2 time (seconds) | AMD A10-6800K time (seconds) | SPEC 2006Cint ratio | Intel Xeon E5-2690 time (seconds) | SPEC 2006Cint ratio | AMD/Intel times ratio | Intel/AMD SPEC ratios |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| perlbench | 9770 | 401 | 24.36 | 261 | 37.43 | 1.54 | 1.54 |
| bzip2 | 9650 | 505 | 19.11 | 422 | 22.87 | 1.20 | 1.20 |
| gcc | 8050 | 490 | 16.43 | 227 | 35.46 | 2.16 | 2.16 |
| mcf | 9120 | 249 | 36.63 | 153 | 59.61 | 1.63 | 1.63 |
| gobink | 10,490 | 418 | 25.10 | 382 | 27.46 | 1.09 | 1.09 |
| hmmer | 9,330 | 182 | 51.26 | 120 | 77.75 | 1.52 | 1.52 |
| sjeng | 12,100 | 517 | 23.40 | 383 | 31.59 | 1.35 | 1.35 |
| libquantum | 20,720 | 84 | 246.08 | 3 | 7295.77 | 29.65 | 29.65 |
| h264ref | 22,130 | 611 | 36.22 | 425 | 52.07 | 1.44 | 1.44 |
| omneipp | 6250 | 313 | 19.97 | 153 | 40.85 | 2.05 | 2.05 |
| astar | 7020 | 303 | 23.17 | 209 | 33.59 | 1.45 | 1.45 |
| xalancbmk | 6900 | 215 | 32.09 | 98 | 70.41 | 2.19 | 2.19 |
| **Geometric mean** | | | **31.91** | | **63.72** | **2.00** | **2.00** |

**Figure 1.19** SPECC2006Cint execution times (in seconds) for the Sun Ultra 5—the reference computer of SPECC2006—and execution times and SPECRatios for the AMD A10 and Intel Xeon E5-2690. The final two columns show the ratios of execution times and SPEC ratios. This figure demonstrates the irrelevance of the reference computer in relative performance. The ratio of the execution times is identical to the ratio of the SPEC ratios, and the ratio of the geometric means ($63.72/31.91 = 2.00$) is identical to the geometric mean of the ratios ($2.00$). Section 1.11 discusses libquantum, whose performance is orders of magnitude higher than the other SPEC benchmarks.

---

<!-- page 53 -->

# 48 $\quad$ Chapter One Fundamentals of Quantitative Design and Analysis

---
## 1.9 Quantitative Principles of Computer Design

Now that we have seen how to define, measure, and summarize performance, cost, dependability, energy, and power, we can explore guidelines and principles that are useful in the design and analysis of computers. This section introduces important observations about design, as well as two equations to evaluate alternatives.

## Take Advantage of Parallelism

Using parallelism is one of the most important methods for improving performance. Every chapter in this book has an example of how performance is enhanced through the exploitation of parallelism. We give three brief examples here, which are expounded on in later chapters.

Our first example is the use of parallelism at the system level. To improve the throughput performance on a typical server benchmark, such as SPEC SFS or TPC-C, multiple processors and multiple storage devices can be used. The workload of handling requests can then be spread among the processors and storage devices, resulting in improved throughput. Being able to expand memory and the number of processors and storage devices is called *scalability*, and it is a valuable asset for servers. Spreading of data across many storage devices for parallel reads and writes enables data-level parallelism. SPEC SFS also relies on request-level parallelism to use many processors, whereas TPC-C uses thread-level parallelism for faster processing of database queries.

At the level of an individual processor, taking advantage of parallelism among instructions is critical to achieving high performance. One of the simplest ways to do this is through pipelining. Pipelining is explained in more detail in [Appendix C] and is a major focus of [Chapter 3]. The basic idea behind pipelining is to overlap instruction execution to reduce the total time to complete an instruction sequence. A key insight into pipelining is that not every instruction depends on its immediate predecessor, so executing the instructions completely or partially in parallel may be possible. Pipelining is the best-known example of ILP.

Parallelism can also be exploited at the level of detailed digital design. For example, set-associative caches use multiple banks of memory that are typically searched in parallel to find a desired item. Arithmetic-logical units use carry lookahead, which uses parallelism to speed the process of computing sums from linear to logarithmic in the number of bits per operand. These are more examples of *data-level* parallelism.

## Principle of Locality

Important fundamental observations have come from properties of programs. The most important program property that we regularly exploit is the *principle of locality*: programs tend to reuse data and instructions they have used recently. A widely held rule of thumb is that a program spends $90\%$ of its execution time in only $10\%$ of the code. An implication of locality is that we can predict with reasonable

---

<!-- page 54 -->

## 1.9 Quantitative Principles of Computer Design 49

accuracy what instructions and data a program will use in the near future based on its accesses in the recent past. The principle of locality also applies to data accesses, though not as strongly as to code accesses.

Two different types of locality have been observed. **Temporal locality** states that recently accessed items are likely to be accessed soon. **Spatial locality** says that items whose addresses are near one another tend to be referenced close together in time. We will see these principles applied in Chapter 2.

### Focus on the Common Case

Perhaps the most important and pervasive principle of computer design is to focus on the common case: in making a design trade-off, favor the frequent case over the infrequent case. This principle applies when determining how to spend resources, because the impact of the improvement is higher if the occurrence is commonplace.

Focusing on the common case works for energy as well as for resource allocation and performance. The instruction fetch and decode unit of a processor may be used much more frequently than a multiplier, so optimize it first. It works on dependability as well. If a database server has 50 storage devices for every processor, storage dependability will dominate system dependability.

In addition, the common case is often simpler and can be done faster than the infrequent case. For example, when adding two numbers in the processor, we can expect overflow to be a rare circumstance and can therefore improve performance by optimizing the more common case of no overflow. This emphasis may slow down the case when overflow occurs, but if that is rare, then overall performance will be improved by optimizing for the normal case.

We will see many cases of this principle throughout this text. In applying this simple principle, we have to decide what the frequent case is and how much performance can be improved by making that case faster. A fundamental law, called **Amdahl's Law**, can be used to quantify this principle.

### Amdahl's Law

The performance gain that can be obtained by improving some portion of a computer can be calculated using Amdahl's Law. Amdahl's Law states that the performance improvement to be gained from using some faster mode of execution is limited by the fraction of the time the faster mode can be used.

Amdahl's Law defines the *speedup* that can be gained by using a particular feature. What is speedup? Suppose that we can make an enhancement to a computer that will improve performance when it is used. Speedup is the ratio

$$\text{Speedup} = \frac{\text{Performance for entire task using the enhancement when possible}}{\text{Performance for entire task without using the enhancement}}$$

Alternatively,

$$\text{Speedup} = \frac{\text{Execution time for entire task without using the enhancement}}{\text{Execution time for entire task using the enhancement when possible}}$$

---

<!-- page 55 -->

50 ■ Chapter One Fundamentals of Quantitative Design and Analysis

Speedup tells us how much faster a task will run using the computer with the enhancement contrary to the original computer.

Amdahl's Law gives us a quick way to find the speedup from some enhancement, which depends on two factors:

1. The fraction of the computation time in the original computer that can be converted to take advantage of the enhancement—For example, if 40 seconds of the execution time of a program that takes 100 seconds in total can use an enhancement, the fraction is $40/100$. This value, which we call $\text{Fraction}_{\mathrm{enhanced}}$, is always less than or equal to 1.

2. The improvement gained by the enhanced execution mode, that is, how much faster the task would run if the enhanced mode were used for the entire program—This value is the time of the original mode over the time of the enhanced mode. If the enhanced mode takes, say, 4 seconds for a portion of the program, while it is 40 seconds in the original mode, the improvement is $40/4$ or 10. We call this value, which is always greater than 1, $\text{Speedup}_{\text{enhanced}}$.

The execution time using the original computer with the enhanced mode will be the time spent using the unenhanced portion of the computer plus the time spent using the enhancement:
$$ \text{Execution time}_{\text{new}} = \text{Execution time}_{\text{old}} \times \left( (1 - \text{Fraction}_{\text{enhanced}}) + \frac{\text{Fraction}_{\text{enhanced}}}{\text{Speedup}_{\text{enhanced}}} \right) $$

The overall speedup is the ratio of the execution times:
$$ \text{Speedup}_{\text{overall}} = \frac{\text{Execution time}_{\text{old}}}{\text{Execution time}_{\text{new}}} = \frac{1}{(1 - \text{Fraction}_{\text{enhanced}}) + \frac{\text{Fraction}_{\text{enhanced}}}{\text{Speedup}_{\text{enhanced}}}} $$

**Example**
Suppose that we want to enhance the processor used for web serving. The new processor is 10 times faster on computation in the web serving application than the old processor. Assuming that the original processor is busy with computation $40\%$ of the time and is waiting for I/O $60\%$ of the time, what is the overall speedup gained by incorporating the enhancement?

**Answer**
$$ \text{Fraction}_{\text{enhanced}} = 0.4; \text{Speedup}_{\text{enhanced}} = 10; \text{Speedup}_{\text{overall}} = \frac{1}{0.6 + \frac{0.4}{10}} = \frac{1}{0.6 + 0.04} = \frac{1}{0.64} \approx 1.56 $$

Amdahl's Law expresses the law of diminishing returns: The incremental improvement in speed gained by an improvement of just a portion of the computation diminishes as improvements are added. An important corollary of Amdahl's Law is that if an enhancement is usable only for a fraction of a task, then we can't speed up the task by more than the reciprocal of 1 minus that fraction.

---

<!-- page 56 -->

## 1.9 Quantitative Principles of Computer Design 51

A common mistake in applying Amdahl's Law is to confuse "fraction of time con-
verted to use an enhancement" and "fraction of time after enhancement is in use."
If, instead of measuring the time that we could use the enhancement in a compu-
tation, we measure the time *after* the enhancement is in use, the results will be
incorrect!

Amdahl's Law can serve as a guide to how much an enhancement will improve
performance and how to distribute resources to improve cost-performance. The
goal, clearly, is to spend resources proportional to where time is spent. Amdahl's
Law is particularly useful for comparing the overall system performance of two
alternatives, but it can also be applied to compare two processor design alterna-
tives, as the following example shows.

**Example** A common transformation required in graphics processors is square root. Imple-
mentations of floating-point (FP) square root vary significantly in performance,
especially among processors designed for graphics. Suppose FP square root
(FSQRT) is responsible for $20\%$ of the execution time of a critical graphics bench-
mark. One proposal is to enhance the FSQRT hardware and speed up this operation
by a factor of 10. The other alternative is just to try to make all FP instructions in the
graphics processor run faster by a factor of 1.6; FP instructions are responsible for
half of the execution time for the application. The design team believes that they
can make all FP instructions run $1.6$ times faster with the same effort as required for
the fast square root. Compare these two design alternatives.

**Answer** We can compare these two alternatives by comparing the speedups:
$$\text{Speedup}_{\text{FSQRT}} = \frac{1}{(1 - 0.2) + \frac{0.2}{10}} = \frac{1}{0.8 + 0.02} = 1.22$$
$$\text{Speedup}_{\text{FP}} = \frac{1}{(1 - 0.5) + \frac{0.5}{1.6}} = \frac{1}{0.5 + 0.3125} = \frac{1}{0.8125} = 1.23$$
Improving the performance of the FP operations overall is slightly better because
of the higher frequency.

Amdahl's Law is applicable beyond performance. Let's redo the reliability
example from page 39 after improving the reliability of the power supply via
redundancy from $200,000$-hour to $830,000,000$-hour MTTF, or $4150 \times$ better.

**Example** The calculation of the failure rates of the disk subsystem was
$$\text{Failure rate}_{\text{system}} = 10 \times \left( \frac{1}{1,000,000} + \frac{1}{500,000} + \frac{1}{200,000} + \frac{1}{200,000} + \frac{1}{1,000,000} \right)$$
$$= \frac{10+2+5+5+1}{1,000,000 \text{ hours}} = \frac{23}{1,000,000 \text{ hours}}$$

---

<!-- page 57 -->

```markdown
**52** ■ Chapter One *Fundamentals of Quantitative Design and Analysis*

Therefore the fraction of the failure rate that could be improved is 5 per million
hours out of 23 for the whole system, or $0.22$.

**Answer** The reliability improvement would be
$$
\text{Improvement}_{\text{power supply pair}} = \frac{1}{(1 - 0.22) + \frac{0.22}{4150}} = \frac{1}{0.78 + \frac{0.22}{4150}} = 1.28
$$

Despite an impressive $4150\times$ improvement in reliability of one module, from the
system's perspective, the change has a measurable but small benefit.

In the preceding examples, we needed the fraction consumed by the new and
improved version; often it is difficult to measure these times directly. In the next
section, we will see another way of doing such comparisons based on the use
of an equation that decomposes the CPU execution time into three separate
components. If we know how an alternative affects these three components,
we can determine its overall performance. Furthermore, it is often possible to
build simulators that measure these components before the hardware is actually
designed.

## The Processor Performance Equation

Essentially all computers are constructed using a clock running at a constant rate.
These discrete time events are called *clock periods, clocks, cycles,* or *clock cycles*.
Computer designers refer to the time of a clock period by its duration (e.g., $1\text{ ns}$) or
by its rate (e.g., $1\text{ GHz}$). CPU time for a program can then be expressed two ways:

$$
\text{CPU time} = \text{CPU clock cycles for a program} \times \text{Clock cycle time}
$$

or

$$
\text{CPU time} = \frac{\text{CPU clock cycles for a program}}{\text{Clock rate}}
$$

In addition to the number of clock cycles needed to execute a program, we can
also count the number of instructions executed—the *instruction path length* or
*instruction count* ($\text{IC}$). If we know the number of clock cycles and the instruction
count, we can calculate the average number of *clock cycles per instruction* ($\text{CPI}$).
Because it is easier to work with, and because we will deal with simple processors
in this chapter, we use $\text{CPI}$. Designers sometimes also use *instructions per clock*
($\text{IPC}$), which is the inverse of $\text{CPI}$.

$\text{CPI}$ is computed as
$$
\text{CPI} = \frac{\text{CPU clock cycles for a program}}{\text{Instruction count}}
$$

This processor figure of merit provides insight into different styles of instruction
sets and implementations, and we will use it extensively in the next four
chapters.
```

---

<!-- page 58 -->

## 1.9 Quantitative Principles of Computer Design $\blacksquare$ 53

By transposing the instruction count in the preceding formula, clock cycles can be defined as $\text{IC} \times \text{CPI}$. This allows us to use CPI in the execution time formula:

$$\text{CPU time} = \text{Instruction count} \times \text{Cycles per instruction} \times \text{Clock cycle time}$$

Expanding the first formula into the units of measurement shows how the pieces fit together:

$$\frac{\text{Instructions}}{\text{Program}} \times \frac{\text{Clock cycles}}{\text{Instruction}} \times \frac{\text{Seconds}}{\text{Clock cycle}} = \frac{\text{Seconds}}{\text{Program}} = \text{CPU time}$$

As this formula demonstrates, processor performance is dependent upon three characteristics: clock cycle (or rate), clock cycles per instruction, and instruction count. Furthermore, CPU time is *equally* dependent on these three characteristics; for example, a $10\%$ improvement in any one of them leads to a $10\%$ improvement in CPU time.

Unfortunately, it is difficult to change one parameter in complete isolation from others because the basic technologies involved in changing each characteristic are interdependent:
* $\text{Clock cycle time} \text{---Hardware technology and organization}$
* $\text{CPI} \text{---Organization and instruction set architecture}$
* $\text{Instruction count} \text{---Instruction set architecture and compiler technology}$

Luckily, many potential performance improvement techniques primarily enhance one component of processor performance with small or predictable impacts on the other two.

In designing the processor, sometimes it is useful to calculate the number of total processor clock cycles as

$$\text{CPU clock cycles} = \sum_{i=1}^{n} \text{IC}_i \times \text{CPI}_i$$

where $\text{IC}_i$ represents the number of times instruction $i$ is executed in a program and $\text{CPI}_i$ represents the average number of clocks per instruction for instruction $i$. This form can be used to express CPU time as

$$\text{CPU time} = \left( \sum_{i=1}^{n} \text{IC}_i \times \text{CPI}_i \right) \times \text{Clock cycle time}$$

and overall CPI as

$$\text{CPI} = \frac{\sum_{i=1}^{n} \text{IC}_i \times \text{CPI}_i}{\text{Instruction count}} = \sum_{i=1}^{n} \frac{\text{IC}_i}{\text{Instruction count}} \times \text{CPI}_i$$

The latter form of the CPI calculation uses each individual $\text{CPI}_i$ and the fraction of occurrences of that instruction in a program (i.e., $\text{IC}_i \div \text{Instruction count}$). Because it must include pipeline effects, cache misses, and any other memory system

---

<!-- page 59 -->

54 ** Chapter One Fundamentals of Quantitative Design and Analysis

inefficiencies, $\text{CPI}_I$, should be measured and not just calculated from a table in the back of a reference manual.

Consider our performance example on page 52, here modified to use measurements of the frequency of the instructions and of the instruction $\text{CPI}$ values, which, in practice, are obtained by simulation or by hardware instrumentation.

**Example** Suppose we made the following measurements:
$$\begin{aligned} \text{Frequency of FP operations} &= 25\% \\ \text{Average CPI of FP operations} &= 4.0 \\ \text{Average CPI of other instructions} &= 1.33 \\ \text{Frequency of FSQRT} &= 2\% \\ \text{CPI of FSQRT} &= 20 \end{aligned}$$

Assume that the two design alternatives are to decrease the $\text{CPI}$ of $\text{FSQRT}$ to 2 or to decrease the average $\text{CPI}$ of all $\text{FP}$ operations to 2.5. Compare these two design alternatives using the processor performance equation.

**Answer** First, observe that only the $\text{CPI}$ changes; the clock rate and instruction count remain identical. We start by finding the original $\text{CPI}$ with neither enhancement:
$$\text{CPI}_{\text{original}} = \sum_{i=1}^n \text{CPI}_i \times \left(\frac{\text{IC}_i}{\text{Instruction count}}\right)$$
$$= (4 \times 25\%) + (1.33 \times 75\%) = 2.0$$
We can compute the $\text{CPI}$ for the enhanced $\text{FSQRT}$ by subtracting the cycles saved from the original $\text{CPI}$:
$$\text{CPI}_{\text{with new FSQRT}} = \text{CPI}_{\text{original}} - 2\% \times (\text{CPI}_{\text{old FSQRT}} - \text{CPI}_{\text{new FSQRT only}})$$
$$= 2.0 - 2\% \times (20 - 2) = 1.64$$
We can compute the $\text{CPI}$ for the enhancement of all $\text{FP}$ instructions the same way or by summing the $\text{FP}$ and non-$\text{FP}$ $\text{CPI}$s. Using the latter gives us
$$\text{CPI}_{\text{new FP}} = (75\% \times 1.33) + (25\% \times 2.5) = 1.625$$
Since the $\text{CPI}$ of the overall $\text{FP}$ enhancement is slightly lower, its performance will be marginally better. Specifically, the speedup for the overall $\text{FP}$ enhancement is
$$\text{Speedup}_{\text{new FP}} = \frac{\text{CPU time}_{\text{original}}}{\text{CPU time}_{\text{new FP}}} = \frac{\text{IC} \times \text{Clock cycle} \times \text{CPI}_{\text{original}}}{\text{IC} \times \text{Clock cycle} \times \text{CPI}_{\text{new FP}}}$$
$$= \frac{\text{CPI}_{\text{original}}}{\text{CPI}_{\text{new FP}}} = \frac{2.00}{1.625} = 1.23$$
Happily, we obtained this same speedup using Amdahl's Law on page 51.

---

<!-- page 60 -->

## 1.10 Putting It All Together: Performance, Price, and Power - 55

It is often possible to measure the constituent parts of the processor performance equation. Such isolated measurements are a key advantage of using the processor performance equation versus Amdahl’s Law in the previous example. In particular, it may be difficult to measure things such as the fraction of execution time for which a set of instructions is responsible. In practice, this would probably be computed by summing the product of the instruction count and the CPI for each of the instructions in the set. Since the starting point is often individual instruction count and CPI measurements, the processor performance equation is incredibly useful.

To use the processor performance equation as a design tool, we need to be able to measure the various factors. For an existing processor, it is easy to obtain the execution time by measurement, and we know the default clock speed. The challenge lies in discovering the instruction count or the CPI. Most processors include counters for both instructions executed and clock cycles. By periodically monitoring these counters, it is also possible to attach execution time and instruction count to segments of the code, which can be helpful to programmers trying to understand and tune the performance of an application. Often designers or programmers will want to understand performance at a more fine-grained level than what is available from the hardware counters. For example, they may want to know why the CPI is what it is. In such cases, the simulation techniques used are like those for processors that are being designed.

Techniques that help with energy efficiency, such as dynamic voltage frequency scaling and overclocking (see Section 1.5), make this equation harder to use, because the clock speed may vary while we measure the program. A simple approach is to turn off those features to make the results reproducible. Fortunately, as performance and energy efficiency are often highly correlated—taking less time to run a program generally saves energy—it’s probably safe to consider performance without worrying about the impact of DVFS or overclocking on the results.

## 1.10 Putting It All Together: Performance, Price, and Power

In the “Putting It All Together” sections that appear near the end of every chapter, we provide real examples that use the principles in that chapter. In this section, we look at measures of performance and power-performance in small servers using the SPECpower benchmark.

Figure 1.20 shows the three multiprocessor servers we are evaluating along with their price. To keep the price comparison fair, all are Dell PowerEdge servers. The first is the PowerEdge R710, which is based on the Intel Xeon $\times$ 85670 micro-processor with a clock rate of 2.93 GHz. Unlike the Intel Core i7-6700 in Chapters 2–5, which has 20 cores and a 40 MB L3 cache, this Intel chip has 22 cores and a 55 MB L3 cache, although the cores themselves are identical. We selected a two-socket system—so 44 cores total—with 128 GB of ECC-protected 2400 MHz DDR4 DRAM. The next server is the PowerEdge C630, with the same processor, number of sockets, and DRAM. The main difference is a smaller rack-mountable package: “2U” high (3.5 inches) for the 730 versus “1U” (1.75 inches) for the 630.

---

<!-- page 61 -->

# 56 $\quad$ Chapter One Fundamentals of Quantitative Design and Analysis

| Component | System 1 | System 2 | System 3 |
|---|---|---|---|
| | Cost ($\%$ Cost) | Cost ($\%$ Cost) | Cost ($\%$ Cost) |
| **Base server** | PowerEdge R710 | $\$653 (7\%)$ | PowerEdge R815 | $\$1437 (15\%)$ | PowerEdge R815 | $\$1437 (11\%)$ |
| **Power supply** | $570\text{ W}$ | | $1100\text{ W}$ | | $1100\text{ W}$ | |
| **Processor** | Xeon X5670 | $\$3738 (40\%)$ | Opteron 6174 | $\$2679 (29\%)$ | Opteron 6174 | $\$5358 (42\%)$ |
| **Clock rate** | $2.93\text{ GHz}$ | | $2.20\text{ GHz}$ | | $2.20\text{ GHz}$ | |
| **Total cores** | 12 | | 24 | | 48 | |
| **Sockets** | 2 | | 2 | | 4 | |
| **Cores/socket** | 6 | | 12 | | 12 | |
| **DRAM** | 12 GB | $\$484 (5\%)$ | 16 GB | $\$693 (7\%)$ | 32 GB | $\$1386 (11\%)$ |
| **Ethernet Inter.** | Dual 1-Gbit | $\$199 (2\%)$ | Dual 1-Gbit | $\$199 (2\%)$ | Dual 1-Gbit | $\$199 (2\%)$ |
| **Disk** | 50 GB SSD | $\$1279 (14\%)$ | 50 GB SSD | $\$1279 (14\%)$ | 50 GB SSD | $\$1279 (10\%)$ |
| **Windows OS** | | $\$2999 (32\%)$ | | $\$2999 (33\%)$ | | $\$2999 (24\%)$ |
| **Total** | | $\$9352 (100\%)$ | | $\$9286 (100\%)$ | | $\$12,658 (100\%)$ |
| **Max ssj\_ops** | 910,978 | | 926,676 | | $1,840,450$ | |
| **Max ssj\_ops/$\$$** | 97 | | 100 | | 145 | |

**Figure 1.20** Three Dell PowerEdge servers being measured and their prices as of July 2016. We calculated the cost of the processors by subtracting the cost of a second processor. Similarly, we calculated the overall cost of memory by seeing what the cost of extra memory was. Hence the base cost of the server is adjusted by removing the estimated cost of the default processor and memory. Chapter 5 describes how these multisocket systems are connected together, and Chapter 6 describes how clusters are connected together.

The third server is a cluster of 16 of the PowerEdge 630s that is connected together with a 1 Gbit/s Ethernet switch. All are running the Oracle Java HotSpot Version 1.7 Java Virtual Machine (JVM) and the Microsoft Windows Server 2012 R2 Datacenter version 6.3 operating system.

Note that because of the forces of benchmarking (see Section 1.11), these are unusually configured servers. The systems in Figure 1.20 have little memory relative to the amount of computation, and just a tiny $120\text{ GB}$ solid-state disk. It is easy to add more cores if you don’t need to add commensurate increases in memory and storage!

Rather than run statically linked C programs of SPEC CPU, SPECpower uses a more modern software stack written in Java. It is based on SPECjbb, and it represents the server side of business applications, with performance measured as the number of transactions per second, called $ssj\_ops$ for *server side Java operations* per second. It exercises not only the processor of the server, as does SPEC CPU, but also the caches, memory system, and even the multiprocessor interconnection system. In addition, it exercises the JVM, including the JIT runtime compiler and garbage collector, as well as portions of the underlying operating system.

As the last two rows of Figure 1.20 show, the performance winner is the cluster of 16 R630s, which is hardly a surprise since it is by far the most expensive. The price-performance winner is the PowerEdge R630, but it barely beats the cluster at 213 versus 211 $ssj\_ops/$\$. Amazingly, the 16 node cluster is within $1\%$ of the same price-performances of a single node despite being 16 times as large.

---

<!-- page 62 -->

## 1.10 Putting It All Together: Performance, Price, and Power $\blacksquare$ 57

While most benchmarks (and most computer architects) care only about performance of systems at peak load, computers rarely run at peak load. Indeed, Figure 6.2 in Chapter 6 shows the results of measuring the utilization of tens of thousands of servers over 6 months at Google, and less than 1% operate at an average utilization of 100%. The majority have an average utilization of between 10% and 50%. Thus the SPECpower benchmark captures power as the target workload varies from its peak in 10% intervals all the way to 0%, which is called Active Idle. Figure 1.21 plots the ssj\_ops (SSJ operations/second) per watt and the average power as the target load varies from $100\%$ to $0\%$. The Intel R730 always has the lowest power and the single node R630 has the best ssj\_ops per watt across each target workload level. Since watts $=$ joules/second, this metric is proportional to SSJ operations per joule:

$$\frac{\text{ssj\_operations}/\text{second}}{\text{Watt}} = \frac{\text{ssj\_operations}/\text{second}}{\text{Joule}/\text{second}} = \frac{\text{ssj\_operations}}{\text{Joule}}$$

[FIGURE: Bar chart comparing power performance (ssj\_ops/watt and Watts) for different Dell server configurations (Dell 630 44 cores, Dell 730 44 cores, Dell 630 cluster 704 cores) across target workloads from 100% down to Active Idle.]

**Figure 1.21** Power performance of the three servers in Figure 1.20. SsJ\_ops/watt values are on the left axis, with the three columns associated with it, and watts are on the right axis, with the three lines associated with it. The horizontal axis shows the target workload, as it varies from 100% to Active Idle. The single node R630 has the best ssj\_ops/watt at each workload level, but R730 consumes the lowest power at each level.

---

<!-- page 63 -->

## Chapter One Fundamentals of Quantitative Design and Analysis

To calculate a single number to use to compare the power efficiency of systems, SPECpower uses

$$\text{Overall ssj\_ops/watt} = \frac{\sum \text{ssj\_ops}}{\sum \text{power}}$$

The overall ssj\_ops/watt of the three servers is $10,802$ for the R730, $11,157$ for the R630, and $10,062$ for the cluster of $16$ R630s. Therefore the single node R630 has the best power-performance. Dividing by the price of the servers, the ssj\_ops/watt/\$1,000 is $879$ for the R730, $899$ for the R630, and $789$ (per node) for the $16$-node cluster of R630s. Thus, after adding power, the single-node R630 is still in first place in performance/price, but now the single-node R730 is significantly more efficient than the $16$-node cluster.

### 1.11 Fallacies and Pitfalls

The purpose of this section, which will be found in every chapter, is to explain some commonly held misbeliefs or misconceptions that you should avoid. We call such misbeliefs *fallacies*. When discussing a fallacy, we try to give a counterexample. We also discuss *pitfalls*—easily made mistakes. Often pitfalls are generalizations of principles that are true in a limited context. The purpose of these sections is to help you avoid making these errors in computers that you design.

**Pitfall** All exponential laws must come to an end.

The first to go was Dennard scaling. Dennard's $1974$ observation was that power density was constant as transistors got smaller. If a transistor's linear region shrank by a factor of $2$, then both the current and voltage were also reduced by a factor of $2$, and so power it used fell by $4$. Thus chips could be designed to operate faster and still use less power. Dennard scaling ended $30$ years after it was observed, not because transistors didn't continue to get smaller but because integrated circuit dependability limited how far current and voltage could drive. The threshold voltage was driven so low that static power became a significant fraction of overall power.

The next deceleration was hard disk drives. Although there was no law for drives, in the past $30$ years the maximum areal density of hard drives—which determines disk capacity—improved by $30\%-100\%$ per year. In more recent years, it has been less than $5\%$ per year. Increasing density per drive has come primarily from adding more platters to a hard disk drive.

Next up was the venerable Moore's Law. It's been a while since the number of transistors per chip doubled every one to two years. For example, the DRAM chip introduced in $2014$ contained $8$B transistors, and we won't have a $16$B transistor DRAM chip in mass production until $2019$, but Moore's Law predicts a $64$B transistor DRAM chip.

Moreover, the actual end of scaling of the planar logic transistor was even predicted to end by $2021$. Figure $1.22$ shows the predictions of the physical gate length

---

<!-- page 64 -->

# 1.11 Fallacies and Pitfalls $\square$ 59

[FIGURE: A line graph titled "Physical gate length ($\text{nm}$)" vs. "Year" (2013 to 2030), showing two data sets: "2013 report" (blue circles) and "2015 report" (red circles). Both show a decreasing trend in physical gate length over time, with the 2015 report predicting slower shrinkage after about 2021.]

**Figure 1.22** Predictions of logic transistor dimensions from two editions of the ITRS report. These reports started in 2001, but 2015 will be the last edition, as the group has disbanded because of waning interest. The only companies that can produce state-of-the-art logic chips today are GlobalFoundries, Intel, Samsung, and TSMC, whereas there were 19 when the first ITRS report was released. With only four companies left, sharing of plans was too hard to sustain. From *IEEE Spectrum*, July 2016, "Transistors will stop shrinking in 2021, Moore's Law Roadmap Predicts," by Rachel Courtland.

of the logic transistor from two editions of the International Technology Roadmap for Semiconductors (ITRS). Unlike the 2013 report that projected gate lengths to reach $5\ \text{nm}$ by $2028$, the 2015 report projects the length stopping at $10\ \text{nm}$ by $2021$. Density improvements thereafter would have to come from ways other than shrinking the dimensions of transistors. It's not as dire as the ITRS suggests, as companies like Intel and TSMC have plans to shrink to $3\ \text{nm}$ gate lengths, but the rate of change is decreasing.

**Figure 1.23** shows the changes in increases in bandwidth over time for microprocessors and DRAM $\text{—}$ which are affected by the end of Dennard scaling $\text{—}$ as well as for disks. The slowing of technology improvements is apparent in the dropping curves. The continued networking improvement is due to advances in fiber optics and a planned change in pulse amplitude modulation (PAM-4) allowing two-bit encoding so as to transmit information at $400\ \text{Gbit/s}$.

---

<!-- page 65 -->

60 $\square$ Chapter One Fundamentals of Quantitative Design and Analysis

[FIGURE: A line graph titled "Relative Bandwidth Improvement" plotted against "Year" (1975 to 2020 on the x-axis, logarithmic scale from 1 to 100,000 on the y-axis) showing four converging/diverging curves: Microprocessor, Network, Memory, and Disk, illustrating relative bandwidth improvement over time.]

**Figure 1.23** Relative bandwidth for microprocessors, networks, memory, and disks over time, based on data in Figure 1.10.

**Fallacy** Multiprocessors are a silver bullet.

The switch to multiple processors per chip around 2005 did not come from some breakthrough that dramatically simplified parallel programming or made it easy to build multicore computers. The change occurred because there was no other option due to the ILP walls and power walls. Multiple processors per chip do not guarantee lower power; it's certainly feasible to design a multicore chip that uses more power. The potential is just that it's possible to continue to improve performance by replacing a high-clock-rate, inefficient core with several lower-clock-rate, efficient cores. As technology to shrink transistors improves, it can shrink both capacitance and the supply voltage a bit so that we can get a modest increase in the

---

<!-- page 66 -->

1.11 Fallacies and Pitfalls 61

number of cores per generation. For example, for the past few years, Intel has been
adding two cores per generation in their higher-end chips.
As we will see in Chapters 4 and 5, performance is now a programmer’s burden. The programmers’ La-Z-Boy era of relying on a hardware designer to make
their programs go faster without lifting a finger is officially over. If programmers
want their programs to go faster with each generation, they must make their programs more parallel.
The popular version of Moore’s law—increasing performance with each generation of technology—is now up to programmers.

**Pitfall** Falling prey to Amdahl’s heartbreaking law.

Virtually every practicing computer architect knows Amdahl’s Law. Despite this,
we almost all occasionally expend tremendous effort optimizing some feature before
we measure its usage. Only when the overall speedup is disappointing do we recall
that we should have measured first before we spent so much effort enhancing it!

**Pitfall** A single point of failure.

The calculations of reliability improvement using Amdahl’s Law on page 53 show
that dependability is no stronger than the weakest link in a chain. No matter how
much more dependable we make the power supplies, as we did in our example, the
single fan will limit the reliability of the disk subsystem. This Amdahl’s Law
observation led to a rule of thumb for fault-tolerant systems to make sure that every
component was redundant so that no single component failure could bring down
the whole system. Chapter 6 shows how a software layer avoids single points of
failure inside WSCs.

**Fallacy** Hardware enhancements that increase performance also improve energy
efficiency, or are at worst energy neutral.

Esmaeilzadeh et al. (2011) measured SPEC2006 on just one core of a 2.67 GHz
Intel Core i7 using Turbo mode (Section 1.5). Performance increased by a factor
of 1.07 when the clock rate increased to 2.94 GHz (or a factor of 1.10), but the i7
used a factor of 1.37 more joules and a factor of 1.47 more watt hours!

**Fallacy** Benchmarks remain valid indefinitely.

Several factors influence the usefulness of a benchmark as a predictor of real performance, and some change over time. A big factor influencing the usefulness of a
benchmark is its ability to resist “benchmark engineering” or “benchmarking.”
Once a benchmark becomes standardized and popular, there is tremendous pressure to improve performance by targeted optimizations or by aggressive interpretation of the rules for running the benchmark. Short kernels or programs that spend
their time in a small amount of code are particularly vulnerable.
For example, despite the best intentions, the initial SPEC89 benchmark suite
included a small kernel, called matrix300, which consisted of eight different
$300 \times 300$ matrix multiplications. In this kernel, 99% of the execution time was
in a single line (see SPEC, 1989). When an IBM compiler optimized this inner loop

---

<!-- page 67 -->

62 $\quad$ Chapter One Fundamentals of Quantitative Design and Analysis

(using a good idea called *blocking*, discussed in Chapters 2 and 4), performance improved by a factor of 9 over a prior version of the compiler! This benchmark tested compiler tuning and was not, of course, a good indication of overall performance, nor of the typical value of this particular optimization.

Figure $1.19$ shows that if we ignore history, we may be forced to repeat it. SPEC CINT2006 had not been updated for a decade, giving compiler writers substantial time to hone their optimizers to this suite. Note that the SPEC ratios of all benchmarks but *libquantum* fall within the range of $16\text{-}52$ for the AMD computer and from $22$ to $78$ for Intel. Libquantum runs about $250$ times faster on AMD and $7300$ times faster on Intel! This “miracle” is a result of optimizations by the Intel compiler that automatically parallelizes the code across $22$ cores and optimizes memory by using bit packing, which packs together multiple narrow-range integers to save memory space and thus memory bandwidth. If we drop this benchmark and recalculate the geometric means, AMD SPEC CINT2006 falls from $31.9$ to $26.5$ and Intel from $63.7$ to $41.4$. The Intel computer is now about $1.5$ times as fast as the AMD computer instead of $2.0$ if we include libquantum, which is surely closer to their real relative performances. SPECCPU2017 dropped *libquantum*.

To illustrate the short lives of benchmarks, Figure $1.17$ on page $43$ lists the status of all $82$ benchmarks from the various SPEC releases; Gcc is the lone survivor from SPEC89. Amazingly, about $70\%$ of all programs from SPEC2000 or earlier were dropped from the next release.

**Fallacy** The rated mean time to failure of disks is $1,200,000$ hours or almost $140$ years, so disks practically never fail.

The current marketing practices of disk manufacturers can mislead users. How is such an MTTF calculated? Early in the process, manufacturers will put thousands of disks in a room, run them for a few months, and count the number that fail. They compute MTTF as the total number of hours that the disks worked cumulatively divided by the number that failed.

One problem is that this number far exceeds the lifetime of a disk, which is commonly assumed to be five years or $43,800$ hours. For this large MTTF to make some sense, disk manufacturers argue that the model corresponds to a user who buys a disk and then keeps replacing the disk every $5$ years—the planned lifetime of the disk. The claim is that if many customers (and their great-grandchildren) did this for the next century, on average they would replace a disk $27$ times before a failure, or about $140$ years.

A more useful measure is the percentage of disks that fail, which is called the *annual failure rate*. Assume $1000$ disks with a $1,000,000$-hour MTTF and that the disks are used $24$ hours a day. If you replaced failed disks with a new one having the same reliability characteristics, the number that would fail in a year $(8760$ hours) is
$$ \text{Failed disks} = \frac{\text{Number of disks} \times \text{Time period}}{\text{MTTF}} = \frac{1000 \text{ disks} \times 8760 \text{ hours/drive}}{1,000,000 \text{ hours/failure}} = 9 $$
Stated alternatively, $0.9\%$ would fail per year, or $4.4\%$ over a $5$-year lifetime.

---

<!-- page 68 -->

1.11 Fallacies and Pitfalls $\square$ 63

Moreover, those high numbers are quoted assuming limited ranges of temperature and vibration; if they are exceeded, then all bets are off. A survey of disk drives in real environments (Gray and van Ingen, 2005) found that 3\%-7\% of drives failed per year, for an MTTF of about $125,000\text{--}300,000$ hours. An even larger study found annual disk failure rates of $2\% \text{--} 10\%$ (Pinheiro et al., 2007). Therefore the real-world MTTF is about $2 \text{--} 10$ times worse than the manufacturer's MTTF.

**Fallacy** Peak performance tracks observed performance.

The only universally true definition of peak performance is "the performance level a computer is guaranteed not to exceed." Figure 1.24 shows the percentage of peak performance for four programs on four multiprocessors. It varies from $5\%$ to $58\%$. Since the gap is so large and can vary significantly by benchmark, peak performance is not generally useful in predicting observed performance.

[FIGURE: Bar chart showing Percentage of peak performance for four programs (Paratec plasma physics, LBMHD materials science, Cactus astrophysics, GTC magnetic fusion) run on four multiprocessors (Power4, Itanium 2, NEC earth simulator, Cray X1). The performance ranges from 5% to 58% of peak performance across the benchmarks and systems.]

**Figure 1.24** Percentage of peak performance for four programs on four multiprocessors scaled to 64 processors. The Earth Simulator and X1 are vector processors (see Chapter 4 and Appendix G). Not only did they deliver a higher fraction of peak performance, but they also had the highest peak performance and the lowest clock rates. Except for the Paratec program, the Power 4 and Itanium 2 systems delivered between $5\%$ and $10\%$ of their peak. From Oliker, L., Canning, A., Carter, J., Shalf, J., Ethier, S., 2004. Scientific computations on modern parallel vector systems. In: Proc. ACM/IEEE Conf. on Supercomputing, November 6–12, 2004, Pittsburgh, Penn., p. 10.

---

<!-- page 69 -->

# Chapter One Fundamentals of Quantitative Design and Analysis

## Pitfall Fault detection can lower availability.

This apparently ironic pitfall is because computer hardware has a fair amount of state that may not always be critical to proper operation. For example, it is not fatal if an error occurs in a branch predictor, because only performance may suffer.

In processors that try to exploit ILP aggressively, not all the operations are needed for correct execution of the program. Mukherjee et al. (2003) found that less than 30% of the operations were potentially on the critical path for the SPEC2000 benchmarks.

The same observation is true about programs. If a register is "dead" in a program—that is, the program will write the register before it is read again—then errors do not matter. If you were to crash the program upon detection of a transient fault in a dead register, it would lower availability unnecessarily.

The Sun Microsystems Division of Oracle lived this pitfall in 2000 with an L2 cache that included parity, but not error correction, in its Sun E3000 to Sun E10000 systems. The SRAMs they used to build the caches had intermittent faults, which when not modified, the processor would simply reread the data from the cache. Because the designers did not protect the cache with ECC (error-correcting code), the operating system had no choice but to report an error to dirty data and crash the program. Field engineers found no problems on inspection in more than 90% of the cases.

To reduce the frequency of such errors, Sun modified the Solaris operating system to "scrub" the cache by having a process that proactively wrote dirty data to memory. Because the processor chips did not have enough pins to add ECC, the only hardware option for dirty data was to duplicate the external cache, using the copy without the parity error to correct the error.

The pitfall is in detecting faults without providing a mechanism to correct them. These engineers are unlikely to design another computer without ECC on external caches.

## 1.12 Concluding Remarks

This chapter has introduced a number of concepts and provided a quantitative framework that we will expand on throughout the book. Starting with the last edition, energy efficiency is the constant companion to performance.

In Chapter 2, we start with the all-important area of memory system design. We will examine a wide range of techniques that conspire to make memory look infinitely large while still being as fast as possible. (Appendix B provides introductory material on caches for readers without much experience and background with them.) As in later chapters, we will see that hardware–software cooperation has become a key to high-performance memory systems, just as it has to highperformance pipelines. This chapter also covers virtual machines, an increasingly important technique for protection.

In Chapter 3, we look at ILP, of which pipelining is the simplest and most common form. Exploiting ILP is one of the most important techniques for building

---

<!-- page 70 -->

1.12 Concluding Remarks $\square$ 65

high-speed uniprocessors. **Chapter 3** begins with an extensive discussion of basic concepts that will prepare you for the wide range of ideas examined in both chapters. **Chapter 3** uses examples that span about 40 years, drawing from one of the first supercomputers (IBM 360/91) to the fastest processors on the market in 2017. It emphasizes what is called the *dynamic or runtime approach* to exploiting ILP. It also talks about the limits to ILP ideas and introduces multithreading, which is further developed in both Chapters 4 and 5. **Appendix C** provides introductory material on pipelining for readers without much experience and background in pipelining. (We expect it to be a review for many readers, including those of our introductory text, *Computer Organization and Design: The Hardware/Software Interface*.)

**Chapter 4** explains three ways to exploit data-level parallelism. The classic and oldest approach is vector architecture, and we start there to lay down the principles of SIMD design. (Appendix G goes into greater depth on vector architectures.) We next explain the SIMD instruction set extensions found in most desktop microprocessors today. The third piece is an in-depth explanation of how modern graphics processing units (GPUs) work. Most GPU descriptions are written from the programmer's perspective, which usually hides how the computer really works. This section explains GPUs from an insider's perspective, including a mapping between GPU jargon and more traditional architecture terms.

**Chapter 5** focuses on the issue of achieving higher performance using multiple processors, or multiprocessors. Instead of using parallelism to overlap individual instructions, multiprocessing uses parallelism to allow multiple instruction streams to be executed simultaneously on different processors. Our focus is on the dominant form of multiprocessors, shared-memory multiprocessors, though we introduce other types as well and discuss the broad issues that arise in any multiprocessor. Here again we explore a variety of techniques, focusing on the important ideas first introduced in the 1980s and 1990s.

**Chapter 6** introduces clusters and then goes into depth on WSCs, which computer architects help design. The designers of WSCs are the professional descendants of the pioneers of supercomputers, such as Seymour Cray, in that they are designing extreme computers. WSCs contain tens of thousands of servers, and the equipment and the building that holds them cost nearly $\$200$ million. The concerns of price-performance and energy efficiency of the earlier chapters apply to WSCs, as does the quantitative approach to making decisions.

**Chapter 7** is new to this edition. It introduces domain-specific architectures as the only path forward for improved performance and energy efficiency given the end of Moore's Law and Dennard scaling. It offers guidelines on how to build effective domain-specific architectures, introduces the exciting domain of deep neural networks, describes four recent examples that take very different approaches to accelerating neural networks, and then compares their cost-performance.

This book comes with an abundance of material online (see Preface for more details), both to reduce cost and to introduce readers to a variety of advanced topics. Figure 1.25 shows them all. Appendices A–C, which appear in the book, will be a review for many readers.

---

<!-- page 71 -->

## Chapter One Fundamentals of Quantitative Design and Analysis

[FIGURE: List of appendices]

| Appendix | Title |
| :--- | :--- |
| A | Instruction Set Principles |
| B | Review of Memory Hierarchies |
| C | Pipelining: Basic and Intermediate Concepts |
| D | Storage Systems |
| E | Embedded Systems |
| F | Interconnection Networks |
| G | Vector Processors in More Depth |
| H | Hardware and Software for VLIW and EPIC |
| I | Large-Scale Multiprocessors and Scientific Applications |
| J | Computer Arithmetic |
| K | Survey of Instruction Set Architectures |
| L | Advanced Concepts on Address Translation |
| M | Historical Perspectives and References |

In Appendix D, we move away from a processor-centric view and discuss issues in storage systems. We apply a similar quantitative approach, but one based on observations of system behavior and using an end-to-end approach to performance analysis. This appendix addresses the important issue of how to store and retrieve data efficiently using primarily lower-cost magnetic storage technologies. Our focus is on examining the performance of disk storage systems for typical I/O-intensive workloads, such as the OLTP benchmarks mentioned in this chapter. We extensively explore advanced topics in RAID-based systems, which use redundant disks to achieve both high performance and high availability. Finally, Appendix D introduces queuing theory, which gives a basis for trading off utilization and latency.

Appendix E applies an embedded computing perspective to the ideas of each of the chapters and early appendices.

Appendix F explores the topic of system interconnect broadly, including wide area and system area networks that allow computers to communicate.

Appendix H reviews VLIW hardware and software, which, in contrast, are less popular than when EPIC appeared on the scene just before the last edition.

Appendix I describes large-scale multiprocessors for use in high-performance computing.

Appendix J is the only appendix that remains from the first edition, and it covers computer arithmetic.

Appendix K provides a survey of instruction architectures, including the 80x86, the IBM 360, the VAX, and many RISC architectures, including ARM, MIPS, Power, RISC-V, and SPARC.

Appendix L is new and discusses advanced techniques for memory management, focusing on support for virtual machines and design of address translation