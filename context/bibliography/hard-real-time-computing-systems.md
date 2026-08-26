<!-- page 1 -->

# Preface

mium blocking time of a process when accessing shared resources. The latter two protocols also prevent deadlocks and chained blocking.

Chapter 8 is dedicated to non-preemptive and limited preemptive scheduling, often used in industrial applications to make task execution more predictable and reduce the run time overhead introduced by arbitrary preemptions. Different solutions are presented, analyzed, and compared in terms of implementation complexity, predictability, and efficacy.

Chapter 9 deals with the problem of real-time scheduling during overload conditions; that is, those situations in which the total processor demand exceeds the available processing time. These conditions are critical for real-time systems, since not all tasks can complete within their timing constraints. This chapter introduces new metrics for evaluating the performance of a system and presents a new class of scheduling algorithms capable of achieving graceful degradation in overload conditions.

Chapter 10 describes some basic guidelines that should be considered during the design and the development of a hard real-time kernel for critical control applications. An example of a small real-time kernel is presented. The problem of time predictable inter-task communication is also discussed, and a particular communication mechanism for exchanging asynchronous messages among periodic tasks is illustrated. The final section shows how the runtime overhead of the kernel can be evaluated and taken into account in the guarantee tests.

Chapter 11 discusses some important issues related to the design of real-time applications. A robot control system is considered as a specific example for illustrating why control applications need real-time computing and how time constraints can be derived from the application requirements, even though they are not explicitly specified by the user. Finally, the basic set of kernel primitives presented in Chapter 9 is used to illustrate a concrete programming example of real-time tasks for sensory processing and control activities.

Chapter 12 concludes the book by presenting a number of real-time operating systems, including standard interfaces (like RT-Posix, APEX, OSEK, and Micro-ITRON), commercial operating systems (like VxWorks, QNX, OSE), and open source kernels (like Shark, Erika, Marte, and Linux real-time extensions). xi

---

<!-- page 2 -->

# 1

## A GENERAL VIEW

### 1.1 INTRODUCTION

Real-time systems are computing systems that must react within precise time constraints to events in the environment. As a consequence, the correct behavior of these systems depends not only on the value of the computation but also on the time at which the results are produced [SR88]. A reaction that occurs too late could be useless or even dangerous. Today, real-time computing plays a crucial role in our society, since an increasing number of complex systems rely, in part or completely, on computer control. Examples of applications that require real-time computing include the following:

*   Chemical and nuclear plant control,
*   control of complex production processes,
*   railway switching systems,
*   automotive applications,
*   flight control systems,
*   environmental acquisition and monitoring,
*   telecommunication systems,
*   medical systems,
*   industrial automation,
*   robotics,

G.C. Buttazzo, *Hard Real-Time Computing Systems: Predictable Scheduling Algorithms and Applications*, Real Time Systems Series 24, DOI 10.1007/978-1-4614-0676-1\_1, $\text{C}$ Springer Science+Business Media, LLC 2011

---

<!-- page 3 -->

2 $\qquad \qquad \qquad \qquad \qquad \qquad \qquad \qquad \qquad \qquad \qquad \text{CHAPTER 1}$

- military systems,
- space missions,
- consumer electronic devices,
- multimedia systems,
- smart toys, and
- virtual reality.

In many cases, the real-time computer running the application is embedded into the system to be controlled. Embedded systems span from small portable devices (e.g., cellular phones, cameras, navigators, ECG Holter devices, smart toys) to larger systems (e.g., industrial robots, cars, aircrafts).

Despite this large application domain, many researchers, developers, and technical managers have serious misconceptions about real-time computing [Sta88], and most of today's real-time control systems are still designed using ad hoc techniques and heuristic approaches. Very often, control applications with stringent time constraints are implemented by writing large portions of code in assembly language, programming timers, writing low-level drivers for device handling, and manipulating task and interrupt priorities. Although the code produced by these techniques can be optimized to run very efficiently, this approach has the following disadvantages:

- **Tedious programming.** The implementation of large and complex applications in assembly language is much more difficult and time consuming than high-level programming. Moreover, the efficiency of the code strongly depends on the programmer's ability.

- **Difficult code understanding.** Except for the programmers who develop the application, very few people can fully understand the functionality of the software produced. Clever hand-coding introduces additional complexity and makes a program more difficult to comprehend.

- **Difficult software maintainability.** As the complexity of the application software increases, the modification of large assembly programs becomes difficult even for the original programmer.

- **Difficult verification of time constraints.** Without the support of specific tools and methodologies for code and schedulability analysis, the verification of timing constraints becomes practically impossible.

---

<!-- page 4 -->

# A General View

The major consequence of this approach is that the control software produced by empirical techniques can be highly unpredictable. If all critical time constraints cannot be verified a priori and the operating system does not include specific mechanisms for handling real-time tasks, the system could apparently work well for a period of time, but it could collapse in certain rare, but possible, situations. The consequences of a failure can sometimes be catastrophic and may injure people, or cause serious damages to the environment.

A high percentage of accidents that occur in nuclear power plants, space missions, or defense systems are often caused by software bugs in the control system. In some cases, these accidents have caused huge economic losses or even catastrophic consequences, including the loss of human lives.

As an example, the first flight of the space shuttle was delayed, at considerable cost, because of a timing bug that arose from a transient overload during system initialization on one of the redundant processors dedicated to the control of the aircraft [Sta88]. Although the shuttle control system was intensively tested, the timing error was not discovered. Later, by analyzing the code of the processes, it was found that there was only a 1 in 67 probability (about 1.5 percent) that a transient overload during initialization could push the redundant processor out of synchronization.

Another software bug was discovered on the real-time control system of the Patriot missiles, used to protect Saudi Arabia during the Gulf War.$^1$ When a Patriot radar sights a flying object, the onboard computer calculates its trajectory and, to ensure that no missiles are launched in vain, it performs a verification. If the flying object passes through a specific location, computed based on the predicted trajectory, then the Patriot is launched against the target, otherwise the phenomenon is classified as a false alarm.

On February 25, 1991, the radar sighted a Scud missile directed at Saudi Arabia, and the onboard computer predicted its trajectory, performed the verification, but classified the event as a false alarm. A few minutes later, the Scud fell on the city of Dhahran, causing injuries and enormous economic damage. Later on, it was discovered that, because of a long interrupt handling routine running with disable interrupts, the real-time clock of the onboard computer was missing some clock interrupts, thus accumulating a delay of about 57 microseconds per minute. The day of the accident, the computer had been working for about 100 hours (an exceptional situation never experienced before), thus accumulating a total delay of 343 milliseconds. Such a delay caused a prediction error in the verification phase of 687 meters! The bug was corrected on

$^1$ L’Espresso, Vol. XXXVIII, No. 14, 5 April 1992, p. 167.

---

<!-- page 5 -->

4 & \multicolumn{2}{c}{CHAPTER 1} \\
\noalign{\smallskip}
\hline
\end{tabular}
\end{center}

February 26, the day after the accident, by inserting a few preemption points inside
the long interrupt handler.

The examples of failures described above show that software testing, although impor-
tant, does not represent a solution for achieving predictability in real-time systems.
This is mainly due to the fact that, in real-time control applications, the program flow
depends on input sensory data and environmental conditions, which cannot be fully
replicated during the testing phase. As a consequence, the testing phase can provide
only a partial verification of the software behavior, relative to the particular subset of
data provided as input.

A more robust guarantee of the performance of a real-time system under all possi-
ble operating conditions can be achieved only by using more sophisticated design
methodologies, combined with a static analysis of the source code and specific oper-
ating systems mechanisms, purposely designed to support computation under timing
constraints. Moreover, in critical applications, the control system must be capable of
handling all anticipated scenarios, including peak load situations, and its design must
be driven by pessimistic assumptions on the events generated by the environment.

In 1949, an aeronautical engineer in the U.S. Air Force, Captain Ed Murphy, observed
the evolution of his experiments and said: “If something can go wrong, it will go
wrong.” Several years later, Captain Ed Murphy became famous around the world,
not for his work in avionics but for his phrase, simple but ineluctable, today known
as *Murphy’s Law* [Blo77, Blo80, Blo88]. Since that time, many other laws on exis-
tential pessimism have been formulated to describe unfortunate events in a humorous
fashion. Due to the relevance that pessimistic assumptions have on the design of real-
time systems, Table 1.1 lists the most significant laws on the topic, which a software
engineer should always keep in mind.

**1.2 WHAT DOES REAL TIME MEAN?**

**1.2.1 THE CONCEPT OF TIME**

The main characteristic that distinguishes real-time computing from other types of
computation is time. Let us consider the meaning of the words *time* and *real* more
closely.

The word *time* means that the correctness of the system depends not only on the logical
result of the computation but also on the time at which the results are produced.

---

<!-- page 6 -->

# A General View

| | |
| :--- | :--- |
| **Murphy's General Law** | |
| | If something can go wrong, it will go wrong. |
| **Murphy's Constant** | |
| | Damage to an object is proportional to its value. |
| **Naeser's Law** | |
| | One can make something bomb-proof, not jinx-proof. |
| **Troutman Postulates** | |
| | 1. Any software bug will tend to maximize the damage. |
| | 2. The worst software bug will be discovered six months after the field test. |
| **Green's Law** | |
| | If a system is designed to be tolerant to a set of faults, there will always exist an idiot so skilled to cause a nontolerated fault. |
| **Corollary** | |
| | Dummies are always more skilled than measures taken to keep them from harm. |
| **Johnson's First Law** | |
| | If a system stops working, it will do it at the worst possible time. |
| **Sodd's Second Law** | |
| | Sooner or later, the worst possible combination of circumstances will happen. |
| **Corollary** | |
| | A system must always be designed to resist the worst possible combination of circumstances. |

Table 1.1 Murphy's laws on real-time systems.

---

<!-- page 7 -->

6
CHAPTER 1

The word *real* indicates that the reaction of the systems to external events must occur during their evolution. As a consequence, the system time (internal time) must be measured using the same time scale used for measuring the time in the controlled environment (external time).

Although the term *real time* is frequently used in many application fields, it is subject to different interpretations, not always correct. Often, people say that a control system operates in real time if it is able to *quickly* react to external events. According to this interpretation, a system is considered to be real-time if it is fast. The term *fast*, however, has a relative meaning and does not capture the main properties that characterize these types of systems.

In nature, living beings act in real time in their habitat independently of their speed. For example, the reactions of a turtle to external stimuli coming from its natural habitat are as effective as those of a cat with respect to its habitat. In fact, although the turtle is much slower than a cat, in terms of absolute speed, the events that it has to deal with are proportional to the actions it can coordinate, and this is a necessary condition for any animal to survive within an environment.

On the contrary, if the environment in which a biological system lives is modified by introducing events that evolve more rapidly than it can handle, its actions will no longer be as effective, and the survival of the animal is compromised. Thus, a quick fly can still be caught by a fly-swatter, a mouse can be captured by a trap, or a cat can be run down by a speeding car. In these examples, the fly-swatter, the trap, and the car represent unusual and anomalous events for the animals, out of their range of capabilities, which can seriously jeopardize their survival. The cartoons in Figure 1.1 schematically illustrate the concept expressed above.

[FIGURE: Cartoons illustrating concept of time and survival]

The previous examples show that the concept of time is not an intrinsic property of a control system, either natural or artificial, but that it is strictly related to the environment in which the system operates. It does not make sense to design a real-time computing system for flight control without considering the timing characteristics of the aircraft.

As a matter of fact, the Ariane 5 accident occurred because the characteristics of the launcher were not taken into account in the implementation of the control software [Bab97, JM97]. On June 4, 1996, the Ariane 5 launcher ended in a failure 37 seconds after initiation of the flight sequence. At an altitude of about 3,700 meters, the launcher started deflecting from its correct path, and a few seconds later it was destroyed by its automated self-destruct system. The failure was caused by an operand error originated in a routine called by the Inertial Reference System for converting accelerometric data from 64-bit floating point to 16-bit signed integer.

---

<!-- page 8 -->

# A General View

[FIGURE: Figure 1.1 illustrating a mouse running towards cheese (a), a turtle moving slowly (b), a mouse trapped in a cage (c), and a fly being squashed by a swatter (d), all related to real-time behavior.]

**Figure 1.1** Both the mouse (a) and the turtle (b) behave in real time with respect to their natural habitat. Nevertheless, the survival of fast animals such as a mouse or a fly can be jeopardized by events (c and d) quicker than their reactive capabilities.

One value was too large to be converted and the program was not explicitly designed to handle the integer overflow error, so the Inertial Reference System halted, as specified in other requirements, leaving the launcher without inertial guidance. The conversion error occurred because the control software was reused from the Ariane 4 vehicle, whose dynamics was different from that of the Ariane 5. In particular, the variable containing the horizontal velocity of the rocket went out of range (since larger than the maximum value planned for the Ariane 4), thus generating the error that caused the loss of guidance.

The examples considered above indicate that the environment is always an essential component of any real-time system. Figure 1.2 shows a block diagram of a typical real-time architecture for controlling a physical system.

Some people erroneously believe that it is not worth investing in real-time research because advances in computer hardware will take care of any real-time requirements. Although advances in computer hardware technology will improve system throughput and will increase the computational speed in terms of millions of instructions per second (MIPS), this does not mean that the timing constraints of an application will be met automatically.

---

<!-- page 9 -->

8 CHAPTER 1

[FIGURE: Block diagram of a generic real-time control system showing the ENVIRONMENT interacting with Sensory System, Actuation System, and Control System within a dashed box.]

**Figure 1.2** Block diagram of a generic real-time control system.

In fact, whereas the objective of fast computing is to minimize the average response time of a given set of tasks, the objective of real-time computing is to meet the individual timing requirement of each task [Sta88].

However short the average response time can be, without a scientific methodology we will never be able to guarantee the individual timing requirements of each task in all possible circumstances. When several computational activities have different timing constraints, average performance has little significance for the correct behavior of the system. To better understand this issue, it is worth thinking about this little story: ${}^2$

*There was a man who drowned crossing a stream with an average depth of six inches.*

Hence, rather than being fast, a real-time computing system should be predictable. And one safe way to achieve predictability is to investigate and employ new methodologies at every stage of the development of an application, from design to testing.

At the process level, the main difference between a real-time and a non-real-time task is that a real-time task is characterized by a *deadline*, which is the maximum time within which it must complete its execution.

${}^2$From John Stankovic's notes.

---

<!-- page 10 -->

# A General View

In critical applications, a result produced after the deadline is not only late but wrong! Depending on the consequences that may occur because of a missed deadline, a real-time task can be distinguished in three categories:

- **Hard:** A real-time task is said to be *hard* if producing the results after its deadline may cause catastrophic consequences on the system under control.
- **Firm:** A real-time task is said to be *firm* if producing the results after its deadline is useless for the system, but does not cause any damage.
- **Soft:** A real-time task is said to be *soft* if producing the results after its deadline has still some utility for the system, although causing a performance degradation.

A real-time operating system that is able to handle hard real-time tasks is called a *hard real-time system*. Typically, real-world applications include hard, firm, and soft activities; therefore a hard real-time system should be designed to handle all such task categories using different strategies. In general, when an application consists of a hybrid task set, all hard tasks should be guaranteed off line, firm tasks should be guaranteed on line, aborting them if their deadline cannot be met, and soft tasks should be handled to minimize their average response time.

Examples of hard tasks can be found in safety-critical systems, and are typically related to sensing, actuation, and control activities, such as the following:

- Sensory data acquisition;
- data filtering and prediction;
- detection of critical conditions;
- data fusion and image processing;
- actuator servoing;
- low-level control of critical system components; and
- action planning for systems that tightly interact with the environment.

Examples of firm activities can be found in networked applications and multimedia systems, where skipping a packet or a video frame is less critical than processing it with a long delay. Thus, they include the following:

---

<!-- page 11 -->

10 CHAPTER 1

- Video playing;
- audio/video encoding and decoding;
- on-line image processing;
- sensory data transmission in distributed systems.

Soft tasks are typically related to system-user interactions. Thus, they include:

- The command interpreter of the user interface;
- handling input data from the keyboard;
- displaying messages on the screen;
- representation of system state variables;
- graphical activities; and
- saving report data.

## 1.2.2 LIMITS OF CURRENT REAL-TIME SYSTEMS

Most of the real-time computing systems used to support control applications are based on kernels [AL86, Rea86, HHP D87, SBG86], which are modified versions of timesharing operating systems. As a consequence, they have the same basic features found in timesharing systems, which are not suited to support real-time activities. The main characteristics of such real-time systems include the following:

- **Multitasking.** A support for concurrent programming is provided through a set of system calls for process management (such as *create, activate, terminate, delay, suspend, and resume*). Many of these primitives do not take time into account and, even worse, introduce unbounded delays on tasks' execution time that may cause hard tasks to miss their deadlines in an unpredictable way.

- **Priority-based scheduling.** This scheduling mechanism is quite flexible, since it allows the implementation of several strategies for process management just by changing the rule for assigning priorities to tasks. Nevertheless, when application tasks have explicit time requirements, mapping timing constraints into a set of priorities may not be simple, especially in dynamic environments. The major problem comes from the fact that these kernels have a limited number of priority levels (typically 128 or 256), whereas task deadlines can vary in a much wider range. Moreover, in dynamic environments, the arrival of a new task may require the remapping of the entire set of priorities.

---

<!-- page 12 -->

# A General View
11

- **Ability to quickly respond to external interrupts.** This feature is usually obtained by setting interrupt priorities higher than process priorities and by reducing the portions of code executed with interrupts disabled. Note that, although this approach increases the reactivity of the system to external events, it introduces unbounded delays on processes’ execution. In fact, an application process will be always interrupted by a driver, even though it is more important than the device that is going to be served. Moreover, in the general case, the number of interrupts that a process can experience during its execution cannot be bounded in advance, since it depends on the particular environmental conditions.

- **Basic mechanisms for process communication and synchronization.** Binary semaphores are typically used to synchronize tasks and achieve mutual exclusion on shared resources. However, if no access protocols are used to enter critical sections, classical semaphores can cause a number of undesirable phenomena, such as priority inversion, chained blocking, and deadlock, which again introduce unbounded delays on real-time activities.

- **Small kernel and fast context switch.** This feature reduces system overhead, thus improving the average response time of the task set. However, a small average response time on the task set does not provide any guarantee on the individual deadlines of the tasks. On the other hand, a small kernel implies limited functionality, which affects the predictability of the system.

- **Support of a real-time clock as an internal time reference.** This is an essential feature for any real-time kernel that handles time-critical activities that interact with the environment. Nevertheless, in most commercial kernels this is the only mechanism for time management. In many cases, there are no primitives for explicitly specifying timing constraints (such as deadlines) on tasks, and there is no mechanism for automatic activation of periodic tasks.

From the above features, it is easy to see that those types of real-time kernels are developed under the same basic assumptions made in timesharing systems, where tasks are considered as unknown activities activated at random instants. Except for the priority, no other parameters are provided to the system. As a consequence, computation times, timing constraints, shared resources, or possible precedence relations among tasks are not considered in the scheduling algorithm, and hence no guarantee can be performed.

The only objectives that can be pursued with these systems is a quick reaction to external events and a “small” average response time for the other tasks. Although this may be acceptable for some soft real-time applications, the lack of any form of guarantee precludes the use of these systems for those control applications that require stringent timing constraints that must be met to ensure a safe behavior of the system.

---

<!-- page 13 -->

12 CHAPTER 1

### 1.2.3 DESIRABLE FEATURES OF REAL-TIME SYSTEMS

Complex control applications that require hard timing constraints on tasks' execution need to be supported by highly predictable operating systems. Predictability can be achieved only by introducing radical changes in the basic design paradigms found in classical timesharing systems.

For example, in any real-time control system, the code of each task is known a priori and hence can be analyzed to determine its characteristics in terms of computation time, resources, and precedence relations with other tasks. Therefore, there is no need to consider a task as an unknown processing entity; rather, its parameters can be used by the operating system to verify its schedulability within the specified timing requirements. Moreover, all hard tasks should be handled by the scheduler to meet their individual deadlines, not to reduce their average response time.

In addition, in any typical real-time application, the various control activities can be seen as members of a team acting together to accomplish one common goal, which can be the control of a nuclear power plant or an aircraft. This means that tasks are not all independent and it is not strictly necessary to support independent address spaces.

In summary, there are some very important basic properties that real-time systems must have to support critical applications. They include the following:

*   **Timeliness.** Results have to be correct not only in their value but also in the time domain. As a consequence, the operating system must provide specific kernel mechanisms for time management and for handling tasks with explicit timing constraints and different criticality.
*   **Predictability.** To achieve a desired level of performance, the system must be analyzable to predict the consequences of any scheduling decision. In safety critical applications, all timing requirements should be guaranteed off line, before putting system in operation. If some task cannot be guaranteed within its time constraint, the system must notify this fact in advance, so that alternative actions can be planned to handle the exception.
*   **Efficiency.** Most of real-time systems are embedded into small devices with severe constraints in terms of space, weight, energy, memory, and computational power. In these systems, an efficient management of the available resources by the operating system is essential for achieving a desired performance.

---

<!-- page 14 -->

A General View
13

*   **Robustness.** Real-time systems must not collapse when they are subject to peak load conditions, so they must be designed to manage all anticipated load scenarios. Overload management and adaptation behavior are essential features to handle systems with variable resource needs and high load variations.
*   **Fault tolerance.** Single hardware and software failures should not cause the system to crash. Therefore, critical components of the real-time system have to be designed to be fault tolerant.
*   **Maintainability.** The architecture of a real-time system should be designed according to a modular structure to ensure that possible system modifications are easy to perform.

## 1.3 ACHIEVING PREDICTABILITY

One of the most important properties that a hard real-time system should have is predictability [SR90]. That is, based on the kernel features and on the information associated with each task, the system should be able to predict the evolution of the tasks and guarantee in advance that all critical timing constraints will be met. The reliability of the guarantee, however, depends on a range of factors, which involve the architectural features of the hardware and the mechanisms and policies adopted in the kernel, up to the programming language used to implement the application.

The first component that affects the predictability of the scheduling is the processor itself. The internal characteristics of the processor, such as instruction prefetch, pipelining, cache memory, and direct memory access (DMA) mechanisms, are the first cause of nondeterminism. In fact, although these features improve the average performance of the processor, they introduce non-deterministic factors that prevent a precise estimation of the worst-case execution times (WCETs). Other important components that influence the execution of the task set are the internal characteristics of the real-time kernel, such as the scheduling algorithm, the synchronization mechanism, the types of semaphores, the memory management policy, the communication semantics, and the interrupt handling mechanism.

In the rest of this chapter, the main sources of nondeterminism are considered in more detail, from the physical level up to the programming level.

---

<!-- page 15 -->

# CHAPTER 1

## 1.3.1 DMA

Direct memory access (DMA) is a technique used by many peripheral devices to transfer data between the device and the main memory. The purpose of DMA is to relieve the central processing unit (CPU) of the task of controlling the input/output (I/O) transfer. Since both the CPU and the I/O device share the same bus, the CPU has to be blocked when the DMA device is performing a data transfer. Several different transfer methods exist.

One of the most common methods is called *cycle stealing*, according to which the DMA device steals a CPU memory cycle in order to execute a data transfer. During the DMA operation, the I/O transfer and the CPU program execution run in parallel. However, if the CPU and the DMA device require a memory cycle at the same time, the bus is assigned to the DMA device and the CPU waits until the DMA cycle is completed. Using the cycle stealing method, there is no way of predicting how many times the CPU will have to wait for DMA during the execution of a task; hence the response time of a task cannot be precisely determined.

A possible solution to this problem is to adopt a different technique, which requires the DMA device to use the memory *time-slice method* [SR88]. According to this method, each memory cycle is split into two adjacent time slots: one reserved for the CPU and the other for the DMA device. This solution is more expensive than cycle stealing but more predictable. In fact, since the CPU and DMA device do not conflict, the response time of the tasks do not increase due to DMA operations and hence can be predicted with higher accuracy.

## 1.3.2 CACHE

The cache is a fast memory that is inserted as a buffer between the CPU and the random access memory (RAM) to speed up processes’ execution. It is physically located after the memory management unit (MMU) and is not visible at the software programming level. Once the physical address of a memory location is determined, the hardware checks whether the requested information is stored in the cache: if it is, data are read from the cache; otherwise the information is taken from the RAM, and the content of the accessed location is copied in the cache along with a set of adjacent locations. In this way, if the next memory access is done to one of these locations, the requested data can be read from the cache, without having to access the memory.

This buffering technique is motivated by the fact that statistically the most frequent accesses to the main memory are limited to a small address space, a phenomenon called

---

<!-- page 16 -->

A General View

15

program locality. For example, it has been observed that with a 1 Mbyte memory and
a 8 Kbyte cache, the data requested from a program are found in the cache 80 percent
of the time ($hit\ ratio$).

The need for having a fast cache appeared when memory was much slower. Today,
however, since memory has an access time almost comparable to that of the cache,
the main motivation for having a cache is not only to speed up process execution but
also to reduce conflicts with other devices. In any case, the cache is considered as a
processor attribute that speeds up the activities of a computer.

In real-time systems, the cache introduces some degree of nondeterminism. In fact,
although statistically the requested data are found in the cache 80 percent of the time,
it is also true that in the other 20 percent of the cases the performance degrades. This
happens because, when data is not found in the cache (cache fault or miss), the access
time to memory is longer, due to the additional data transfer from RAM to cache.
Furthermore, when performing write operations in memory, the use of the cache is
even more expensive in terms of access time, because any modification made on the
cache must be copied to the memory in order to maintain data consistency. Statistical
observations show that 90 percent of the memory accesses are for read operations,
whereas only 10 percent are for writes. Statistical observations, however, can provide
only an estimation of the average behavior of an application, but cannot be used for
deriving worst-case bounds.

In preemptive systems, the cache behavior is also affected by the number of preemp-
tions. In fact, preemption destroys program locality and heavily increases the number
of cache misses due to the lines evicted by the preempting task. Moreover, the cache-
related preemption delay (CRPD) depends on the specific point at which preemption
takes place; therefore it is very difficult to precisely estimate [AG08, GA07]. Bui et al.
[BCSM08] showed that on a PowerPC MPC7410 with 2 MByte two-way associative
L2 cache the WCET increment due to cache interference can be as large as 33 percent
of the WCET measured in non-preemptive mode.

### 1.3.3 INTERRUPTS

Interrupts generated by I/O peripheral devices represent a big problem for the pre-
dictability of a real-time system because, if not properly handled, they can introduce
unbounded delays during process execution. In almost any operating system, the ar-
rival of an interrupt signal causes the execution of a service routine ($driver$), dedicated
to the management of its associated device. The advantage of this method is to encap-
sulate all hardware details of the device inside the driver, which acts as a server for the

---

<!-- page 17 -->

16

CHAPTER 1

application tasks. For example, in order to get data from an I/O device, each task must
enable the hardware to generate interrupts, wait for the interrupt, and read the data
from a memory buffer shared with the driver, according to the following protocol:

```
<enable device interrupts>
<wait for interrupt>
<get the result>
```

In many operating systems, interrupts are served using a fixed priority scheme, accord-
ing to which each driver is scheduled based on a static priority, higher than process
priorities. This assignment rule is motivated by the fact that interrupt handling routines
usually deal with I/O devices that have real-time constraints, whereas most applica-
tion programs do not. In the context of real-time systems, however, this assumption is
certainly not valid, because a control process could be more urgent than an interrupt
handling routine. Since, in general, it is very difficult to bound a priori the number of
interrupts that a task may experience, the delay introduced by the interrupt mechanism
on tasks’ execution becomes unpredictable.

In order to reduce the interference of the drivers on the application tasks and still
perform I/O operations with the external world, the peripheral devices must be handled
in a different way. In the following, three possible techniques are illustrated.

APPROACH A

The most radical solution to eliminate interrupt interference is to disable all external
interrupts, except the one from the timer (necessary for basic system operations). In
this case, all peripheral devices must be handled by the application tasks, which have
direct access to the registers of the interfacing boards. Since no interrupt is generated,
data transfer takes place through polling.

The direct access to I/O devices allows great programming flexibility and eliminates
the delays caused by the drivers’ execution. As a result, the time needed for trans-
ferring data can be precisely evaluated and charged to the task that performs the op-
eration. Another advantage of this approach is that the kernel does not need to be
modified as the I/O devices are replaced or added.

The main disadvantage of this solution is a low processor efficiency on I/O operations,
due to the busy wait of the tasks while accessing the device registers. Another minor
problem is that the application tasks must have the knowledge of all low-level details
of the devices that they want to handle. However, this can be easily solved by encap-

---

<!-- page 18 -->

A General View

17

sulating all device-dependent routines in a set of library functions that can be called by the application tasks. This approach is adopted in RK, a research hard real-time kernel designed to support multisensory robotics applications [LKP88].

## APPROACH B

As in the previous approach, all interrupts from external devices are disabled, except the one from the timer. Unlike the previous solution, however, the devices are not directly handled by the application tasks but are managed in turn by dedicated kernel routines, periodically activated by the timer.

This approach eliminates the unbounded delays due to the execution of interrupt drivers and confines all I/O operations to one or more periodic kernel tasks, whose computa- tional load can be computed once and for all and taken into account through a specific utilization factor. In some real-time systems, I/O devices are subdivided into two classes based on their speed: slow devices are multiplexed and served by a single cyclical I/O process running at a low rate, whereas fast devices are served by ded- icated periodic system tasks running at higher frequencies. The advantage of this approach with respect to the previous one is that all hardware details of the peripheral devices can be encapsulated into kernel procedures and do not need to be known to the application tasks.

Because the interrupts are disabled, the major problem of this approach is due to the busy wait of the kernel I/O handling routines, which makes the system less efficient during the I/O operations. With respect to the previous approach, this case is charac- terized by a higher system overhead, due to the communication required among the application tasks and the I/O kernel routines for exchanging I/O data. Finally, since the device handling routines are part of the kernel, it has to be modified when some device is replaced or added. This type of solution is adopted in the MARS system [DRSK89, KDK+89].

## APPROACH C

A third approach that can be adopted in real-time systems to deal with the I/O devices is to leave all external interrupts enabled, while reducing the drivers to the least pos- sible size. According to this method, the only purpose of each driver is to activate a proper task that will take care of the device management. Once activated, the de- vice manager task executes under the direct control of the operating system, and it is guaranteed and scheduled just like any other application task. In this way, the priority that can be assigned to the device handling task is completely independent from other

---

<!-- page 19 -->

priorities and can be set according to the application requirements. Thus, a control task can have a higher priority than a device handling task.

The idea behind this approach is schematically illustrated in Figure 1.3. The occurrence of event $E$ generates an interrupt, which causes the execution of a driver associated with that interrupt. Unlike the traditional approach, this driver does not handle the device directly but only activates a dedicated task, $J_E$, which will be the actual device manager.

$$\text{
\begin{array}{c}
\text{Driver associated} \\ \text{with event } E
\end{array}
\quad \longrightarrow \quad
\begin{array}{|c|}
\hline
\text{Activation} \\ \text{of task} \\ J_E \\ \hline
\end{array}
\quad \longrightarrow \quad
\begin{array}{c}
\text{Task } J_E \\ \quad \\
\begin{array}{|c|}
\hline
\text{Handling} \\ \text{of event} \\ E \\ \hline
\end{array}
\end{array}
}$$
event $E \quad \longleftarrow$

**Figure 1.3** Activation of a device-handling task.

The major advantage of this approach with respect to the previous ones is to eliminate the busy wait during I/O operations. Moreover, compared to the traditional technique, the unbounded delays introduced by the drivers during tasks' execution are also drastically reduced (although not completely removed), so the task execution times become more predictable. As a matter of fact, a little unbounded overhead due to the execution of the small drivers still remains in the system, and it should be taken into account in the guarantee mechanism. However, it can be neglected in most practical cases. This type of solution are used in the ARTS system [TK88, TM89], in HARTIK [BDN93, But93], and in SPRING [SR91].

### 1.3.4 SYSTEM CALLS

System predictability also depends on how the kernel primitives are implemented. In order to precisely evaluate the worst-case execution time of each task, all kernel calls should be characterized by a bounded execution time, used by the guarantee mechanism while performing the schedulability analysis of the application. In addition, in order to simplify this analysis, it is desirable that each kernel primitive be preemptable. In fact, any non-preemptable section could possibly delay the activation or the execution of critical activities, causing a timing fault to hard deadlines.

---

<!-- page 20 -->

A General View

19

## 1.3.5 SEMAPHORES

The typical semaphore mechanism used in traditional operating systems is not suited for implementing real-time applications because it is subject to the priority inversion phenomenon, which occurs when a high-priority task is blocked by a low-priority task for an unbounded interval of time. Priority inversion must absolutely be avoided in real-time systems, since it introduces nondeterministic delays on the execution of critical tasks.

For the mutual exclusion problem, priority inversion can be avoided by adopting particular protocols that must be used every time a task wants to enter a critical section. For instance, efficient solutions are provided by *Basic Priority Inheritance* [SRL90], *Priority Ceiling* [SRL90], and *Stack Resource Policy* [Bak91]. These protocols will be described and analyzed in Chapter 7. The basic idea behind these protocols is to modify the priority of the tasks based on the current resource usage and control the resource assignment through a test executed at the entrance of each critical section. The aim of the test is to bound the maximum blocking time of the tasks that share critical sections.

The implementation of such protocols may require a substantial modification of the kernel, which concerns not only the *wait* and *signal* calls but also some data structures and mechanisms for task management.

## 1.3.6 MEMORY MANAGEMENT

Similarly to other kernel mechanisms, memory management techniques must not introduce nondeterministic delays during the execution of real-time activities. For example, demand paging schemes are not suitable to real-time applications subject to rigid time constraints because of the large and unpredictable delays caused by page faults and page replacements. Typical solutions adopted in most real-time systems adhere to a memory segmentation rule with a fixed memory management scheme. Static partitioning is particularly efficient when application programs require similar amounts of memory.

In general, static allocation schemes for resources and memory management increase the predictability of the system but reduce its flexibility in dynamic environments. Therefore, depending on the particular application requirements, the system designer has to make the most suitable choices for balancing predictability against flexibility.

---

<!-- page 21 -->

## 20

## CHAPTER 1

## 1.3.7 PROGRAMMING LANGUAGE

Besides the hardware characteristics of the physical machine and the internal mechanisms implemented in the kernel, there are other factors that can determine the predictability of a real-time system. One of these factors is certainly the programming language used to develop the application. As the complexity of real-time systems increases, high demand will be placed on the programming abstractions provided by languages.

Unfortunately, current programming languages are not expressive enough to prescribe certain timing behavior and hence are not suited for realizing predictable real-time applications. For example, the Ada language (required by the Department of Defense of the United States for implementing embedded real-time concurrent applications) does not allow the definition of explicit time constraints on tasks’ execution. The `delay` statement puts only a lower bound on the time the task is suspended, and there is no language support to guarantee that a task cannot be delayed longer than a desired upper bound. The existence of nondeterministic constructs, such as the `select` statement, prevents the performing of a reliable worst-case analysis of the concurrent activities. Moreover, the lack of protocols for accessing shared resources allows a high-priority task to wait for a low-priority task for an unbounded duration. As a consequence, if a real-time application is implemented using the Ada language, the resulting timing behavior of the system is likely to be unpredictable.

Recently, new high-level languages have been proposed to support the development of hard real-time applications. For example, *Real-Time Euclid* [KS86] is a programming language specifically designed to address reliability and guaranteed schedulability issues in real-time systems. To achieve this goal, *Real-Time Euclid* forces the programmer to specify time bounds and timeout exceptions in all loops, waits, and device accessing statements. Moreover, it imposes several programming restrictions, such as the ones listed below:

*   **Absence of dynamic data structures.** Third-generation languages normally permit the use of dynamic arrays, pointers, and arbitrarily long strings. In real-time languages, however, these features must be eliminated because they would prevent a correct evaluation of the time required to allocate and deallocate dynamic structures.
*   **Absence of recursion.** If recursive calls were permitted, the schedulability analyzer could not determine the execution time of subprograms involving recursion or how much storage will be required during execution.

---

<!-- page 22 -->

A General View
21

- **Time-bounded loops.** In order to estimate the duration of the cycles at compile time, Real-Time Euclid forces the programmer to specify for each loop construct the maximum number of iterations.

Real-Time Euclid also allows the classification of processes as periodic or aperiodic and provides statements for specifying task timing constraints, such as activation time and period, as well as system timing parameters, such as the time resolution.

Another high-level language for programming hard real-time applications is *Real-Time Concurrent C* [GR91]. It extends Concurrent C by providing facilities to specify periodicity and deadline constraints, to seek guarantees that timing constraints will be met, and to perform alternative actions when either the timing constraints cannot be met or guarantees are not available. With respect to Real-Time Euclid, which has been designed to support static real-time systems, where guarantees are made at compile time, Real-Time Concurrent C is oriented to dynamic systems, where tasks can be activated at run time. Another important feature of Real-Time Concurrent C is that it permits the association of a deadline with any statement, using the following construct:

```
within deadline $(d)$ statement-1
[else statement-2]
```

If the execution of *statement-1* starts at time $t$ and is not completed at time $(t+d)$, then its execution is terminated and *statement-2*, if specified, is executed.

Clearly, any real-time construct introduced in a language must be supported by the operating system through dedicated kernel services, which must be designed to be efficient and analyzable. Among all kernel mechanisms that influence predictability, the scheduling algorithm is certainly the most important factor, since it is responsible for satisfying timing and resource contention requirements.

In the rest of this book, several scheduling algorithms are illustrated and analyzed under different constraints and assumptions. Each algorithm is characterized in terms of performance and complexity to assist a designer in the development of reliable real-time applications.

---

<!-- page 23 -->

# 2
## BASIC CONCEPTS

## 2.1 INTRODUCTION

Over the last few years, several algorithms and methodologies have been proposed in the literature to improve the predictability of real-time systems. In order to present these results we need to define some basic concepts that will be used throughout the book. We begin with the most important software entity treated by any operating system, the *process*. A process is a computation that is executed by the CPU in a sequential fashion. In this text, the term *process* is used as synonym of *task* and *thread*. However, it is worth saying that some authors prefer to distinguish them and define a process as a more complex entity that can be composed by many concurrent tasks (or threads) sharing a common memory space.

When a single processor has to execute a set of concurrent tasks – that is, tasks that can overlap in time – the CPU has to be assigned to the various tasks according to a predefined criterion, called a *scheduling policy*. The set of rules that, at any time, determines the order in which tasks are executed is called a *scheduling algorithm*. The specific operation of allocating the CPU to a task selected by the scheduling algorithm is referred as *dispatching*.

Thus, a task that could potentially execute on the CPU can be either in execution (if it has been selected by the scheduling algorithm) or waiting for the CPU (if another task is executing). A task that can potentially execute on the processor, independently on its actual availability, is called an *active task*. A task waiting for the processor is called a *ready task*, whereas the task in execution is called a *running task*. All ready tasks waiting for the processor are kept in a queue, called *ready queue*. Operating systems that handle different types of tasks may have more than one ready queue.

G.C. Buttazzo, *Hard Real-Time Computing Systems: Predictable Scheduling Algorithms and Applications*, Part I, Times Series 24, DOI 10.1007/978-1-4614-0676-1\_2,
© Springer Science+Business Media, LLC 2011 23

---

<!-- page 24 -->

```markdown
24 CHAPTER 2

[FIGURE: A diagram showing the states of a task: activation, scheduling, preemption, dispatching, execution, and termination, with arrows indicating transitions.]

**Figure 2.1** Queue of ready tasks waiting for execution.

In many operating systems that allow dynamic task activation, the running task can be interrupted at any point, so that a more important task that arrives in the system can immediately gain the processor and does not need to wait in the ready queue. In this case, the running task is interrupted and inserted in the ready queue, while the CPU is assigned to the most important ready task that just arrived. The operation of suspending the running task and inserting it into the ready queue is called **preemption**. Figure 2.1 schematically illustrates the concepts presented above. In dynamic real-time systems, preemption is important for three reasons [SZ92]:

*   Tasks performing exception handling may need to preempt existing tasks so that responses to exceptions may be issued in a timely fashion.
*   When tasks have different levels of criticality (expressing task importance), preemption permits executing the most critical tasks, as soon as they arrive.
*   Preemptive scheduling typically allows higher efficiency, in the sense that it allows executing a real-time task sets with higher processor utilization.

On the other hand, preemption destroys program locality and introduces a runtime overhead that inflates the execution time of tasks. As a consequence, limiting preemption in real-time schedules can have beneficial effects in terms of schedulability. This issue will be investigated in Chapter 8.

Given a set of tasks, $J = \{J_1, \ldots, J_n\}$, a **schedule** is an assignment of tasks to the processor, so that each task is executed until completion. More formally, a schedule can be defined as a function $\sigma: \mathbf{R}^+ \to \mathbf{N}$ such that $\forall t \in \mathbf{R}^+, \exists t_1, t_2$ such that $t \in [t_1, t_2)$ and $\forall t' \in [t_1, t_2) \quad \sigma(t') = \sigma(t)$. In other words, $\sigma(t)$ is an integer step function and $\sigma(t) = k$, with $k > 0$, means that task $J_k$ is executing at time $t$, while $\sigma(t) = 0$ means that the CPU is idle. Figure 2.2 shows an example of schedule obtained by executing three tasks: $J_1, J_2, J_3$.
```

---

<!-- page 25 -->

# Basic Concepts

[FIGURE: Schedule obtained by executing three tasks $J_1$, $J_2$, and $J_3$. The schedule shows timeline $t$ on the x-axis and task index $\sigma(t)$ on the y-axis. At time $t_1, t_2, t_3$, task changes occur: $\sigma(t)=1$ for $t_1 \le t < t_2$, $\sigma(t)=2$ for $t_2 \le t < t_3$, and $\sigma(t)=3$ for $t_3 \le t < t_4$. Intervals before $t_1$ and after $t_4$ are idle.]

**Figure 2.2** Schedule obtained by executing three tasks $J_1$, $J_2$, and $J_3$.

* At times $t_1, t_2, t_3$, and $t_4$, the processor performs a **context switch**.
* Each interval $[t_i, t_{i+1})$ in which $\sigma(t)$ is constant is called **time slice**. Interval $[x, y)$ identifies all values of $t$ such that $x \le t < y$.
* A **preemptive schedule** is a schedule in which the running task can be arbitrarily suspended at any time, to assign the CPU to another task according to a predefined scheduling policy. In preemptive schedules, tasks may be executed in disjoint interval of times.
* A schedule is said to be **feasible** if all tasks can be completed according to a set of specified constraints.
* A set of tasks is said to be **schedulable** if there exists at least one algorithm that can produce a feasible schedule.

An example of preemptive schedule is shown in Figure 2.3.

## 2.2 TYPES OF TASK CONSTRAINTS

Typical constraints that can be specified on real-time tasks are of three classes: timing constraints, precedence relations, and mutual exclusion constraints on shared resources.

---

<!-- page 26 -->

26 $\quad$ CHAPTER 2

[FIGURE: A timing diagram showing three jobs $J_1, J_2, J_3$ executing over time $t$ with preemption. Below this, a graph $\sigma(t)$ shows the output value over time $t$, illustrating a preemptive schedule.]
**Figure 2.3** Example of a preemptive schedule.

## 2.2.1 TIMING CONSTRAINTS

Real-time systems are characterized by computational activities with stringent timing constraints that must be met in order to achieve the desired behavior. A typical timing constraint on a task is the *deadline*, which represents the time before which a process should complete its execution without causing any damage to the system. If a deadline is specified with respect to the task arrival time, it is called a *relative deadline*, whereas if it is specified with respect to time zero, it is called an *absolute deadline*. Depending on the consequences of a missed deadline, real-time tasks are usually distinguished in three categories:

*   **Hard:** A real-time task is said to be *hard* if missing its deadline may cause catastrophic consequences on the system under control.
*   **Firm:** A real-time task is said to be *firm* if missing its deadline does not cause any damage to the system, but the output has no value.
*   **Soft:** A real-time task is said to be *soft* if missing its deadline has still some utility for the system, although causing a performance degradation.

In general, a real-time task $\tau_i$ can be characterized by the following parameters:

---

<!-- page 27 -->

# Basic Concepts
27

[FIGURE: Timeline diagram illustrating the typical parameters of a real-time task, $t_i$, arrival time $a_i$, start time $s_i$, computation time $C_i$, finishing time $f_i$, absolute deadline $d_i$, and relative deadline $D_i$.]

**Figure 2.4** Typical parameters of a real-time task.

*   **Arrival time** $a_i$ is the time at which a task becomes ready for execution; it is also referred as *request time* or *release time* and indicated by $r_i$;
*   **Computation time** $C_i$ is the time necessary to the processor for executing the task without interruption;
*   **Absolute Deadline** $d_i$ is the time before which a task should be completed to avoid damage to the system;
*   **Relative Deadline** $D_i$ is the difference between the absolute deadline and the request time: $D_i = d_i - r_i$;
*   **Start time** $s_i$ is the time at which a task starts its execution;
*   **Finishing time** $f_i$ is the time at which a task finishes its execution;
*   **Response time** $R_i$ is the difference between the finishing time and the request time: $R_i = f_i - r_i$;
*   **Criticality** is a parameter related to the consequences of missing the deadline (typically, it can be hard, firm, or soft);
*   **Value** $v_i$ represents the relative importance of the task with respect to the other tasks in the system;
*   **Lateness** $L_i$: $L_i = f_i - d_i$ represents the delay of a task completion with respect to its deadline; note that if a task completes before the deadline, its lateness is negative;
*   **Tardiness or Exceeding time** $E_i$: $E_i = \max(0, L_i)$ is the time a task stays active after its deadline;
*   **Laxity or Slack time** $X_i$: $X_i = d_i - a_i - C_i$ is the maximum time a task can be delayed on its activation to complete within its deadline.

Some of the parameters defined above are illustrated in Figure 2.4.

---

<!-- page 28 -->

# 28

## CHAPTER 2

[FIGURE: Sequence of instances for a periodic task ($\tau_i$) and an aperiodic job ($J_i$). Panel (a) shows the periodic task instance timing with phase $\phi_i$, deadline $D_i$, computation time $C_i$, and period $T_i$. Panel (b) shows the aperiodic job instances with arrival times $a_{i1}, a_{i2}, \dots$ and relative deadlines $d_{i1}, d_{i2}, \dots$]

**Figure 2.5** Sequence of instances for a periodic task (a) and an aperiodic job (b).

Another timing characteristic that can be specified on a real-time task concerns the regularity of its activation. In particular, tasks can be defined as *periodic* or *aperiodic*. Periodic tasks consist of an infinite sequence of identical activities, called *instances* or *jobs*, that are regularly activated at a constant rate. For the sake of clarity, from now on, a periodic task will be denoted by $\tau_i$, whereas an aperiodic job by $J_i$. The generic $k^{\text{th}}$ job of a periodic task $\tau_i$ will be denoted by $\tau_{i,k}$.

The activation time of the first periodic instance ($\tau_{i,1}$) is called *phase*. If $\phi_i$ is the phase of task $\tau_i$, the activation time of the $k^{\text{th}}$ instance is given by $a_{i,k} = \phi_i + (k-1)T_i$, where $T_i$ is the activation *period* of the task. In many practical cases, a periodic process can be completely characterized by its phase $\phi_i$, its computation time $C_i$, its period $T_i$, and its relative deadline $D_i$.

Aperiodic tasks also consist of an infinite sequence of identical jobs (or instances); however, their activations are not regularly interleaved. An aperiodic task where consecutive jobs are separated by a minimum inter-arrival time is called a *sporadic task*. Figure 2.5 shows an example of task instances for a periodic and an aperiodic task.

## 2.2.2 PRECEDENCE CONSTRAINTS

In certain applications, computational activities cannot be executed in arbitrary order but have to respect some precedence relations defined at the design stage. Such precedence relations are usually described through a directed acyclic graph $G$, where tasks

---

<!-- page 29 -->

# Basic Concepts
29

[FIGURE: Directed acyclic graph representing precedence relations among five tasks $J_1$ through $J_5$.]

$$\begin{array}{ccl} J_1 & \prec & J_2 \\ J_1 & \longrightarrow & J_2 \\ J_1 & \prec & J_4 \\ J_1 & \not\prec & J_4 \end{array}$$

**Figure 2.6** Precedence relations among five tasks.

are represented by nodes and precedence relations by arrows. A precedence graph $G$ induces a partial order on the task set.

* The notation $J_a \prec J_b$ specifies that task $J_a$ is a **predecessor** of task $J_b$, meaning that $G$ contains a directed path from node $J_a$ to node $J_b$.
* The notation $J_a \longrightarrow J_b$ specifies that task $J_a$ is an **immediate predecessor** of $J_b$, meaning that $G$ contains an arc directed from node $J_a$ to node $J_b$.

Figure 2.6 illustrates a directed acyclic graph that describes the precedence constraints among five tasks. From the graph structure we observe that task $J_1$ is the only one that can start executing since it does not have predecessors. Tasks with no predecessors are called *beginning tasks*. As $J_1$ is completed, either $J_2$ or $J_3$ can start. Task $J_4$ can start only when $J_2$ is completed, whereas $J_5$ must wait for the completion of $J_2$ and $J_3$. Tasks with no successors, as $J_4$ and $J_5$, are called *ending tasks*.

In order to understand how precedence graphs can be derived from tasks' relations, let us consider the application illustrated in Figure 2.7. Here, a number of objects moving on a conveyor belt must be recognized and classified using a stereo vision system, consisting of two cameras mounted in a suitable location. Suppose that the recognition process is carried out by integrating the two-dimensional features of the top view of the objects with the height information extracted by the pixel disparity on the two images. As a consequence, the computational activities of the application can be organized by defining the following tasks:

---

<!-- page 30 -->

30 CHAPTER 2

[FIGURE: A diagram showing two cameras positioned above a conveyor belt carrying objects of various shapes (a rectangular prism, a cylinder, and a prism with a slanted face).]

**Figure 2.7** Industrial application that requires a visual recognition of objects on a conveyor belt.

*   Two tasks (one for each camera) dedicated to image acquisition, whose objective is to transfer the image from the camera to the processor memory (they are identified by $acq1$ and $acq2$);
*   Two tasks (one for each camera) dedicated to low-level image processing (typical operations performed at this level include digital filtering for noise reduction and edge detection; we identify these tasks as $edge1$ and $edge2$);
*   A task for extracting two-dimensional features from the object contours (it is referred as $shape$);
*   A task for computing the pixel disparities from the two images (it is referred as $disp$);
*   A task for determining the object height from the results achieved by the $disp$ task (it is referred as $H$);
*   A task performing the final recognition (this task integrates the geometrical features of the object contour with the height information and tries to match these data with those stored in the data base; it is referred as $rec$).

From the logic relations existing among the computations, it is easy to see that tasks $acq1$ and $acq2$ can be executed in parallel before any other activity. Tasks $edge1$ and $edge2$ can also be executed in parallel, but each task cannot start before the associated

---

<!-- page 31 -->

Basic Concepts 31

[FIGURE: Precedence task graph with nodes acq1, acq2, edge1, edge2, disp, shape, H, and rec, and directed edges showing task dependencies. acq1 leads to edge1, acq2 leads to edge2. edge1 and edge2 both lead to disp and shape. disp leads to H. H and shape both lead to rec.]

Figure 2.8 Precedence task graph associated with the industrial application illustrated in Figure 2.7.

acquisition task completes. Task $shape$ is based on the object contour extracted by the low-level image processing; therefore, it must wait for the termination of both $edge1$ and $edge2$. The same is true for task $disp$, which however can be executed in parallel with task $shape$. Then, task $H$ can only start as $disp$ completes and, finally, task $rec$ must wait the completion of $H$ and $shape$. The resulting precedence graph is shown in Figure 2.8.

## 2.2.3 RESOURCE CONSTRAINTS

From a process point of view, a $resource$ is any software structure that can be used by the process to advance its execution. Typically, a resource can be a data structure, a set of variables, a main memory area, a file, a piece of program, or a set of registers of a peripheral device. A resource dedicated to a particular process is said to be $private$, whereas a resource that can be used by more tasks is called a $shared resource$.

To maintain data consistency, many shared resources do not allow simultaneous accesses by competing tasks, but require their mutual exclusion. This means that a task cannot access a resource $R$ if another task is inside $R$ manipulating its data structures. In this case, $R$ is called a $mutually exclusive\ resource$. A piece of code executed under mutual exclusion constraints is called a $critical\ section$.

---

<!-- page 32 -->

32
CHAPTER 2

$$
\begin{array}{ccc}
\tau_W & R & \tau_D \\
\small\text{---} & \text{int } x=1; & \small\text{---} \\
\small\text{---} & \text{int } y=2; & \small\text{---} \\
\small\text{---} & & \small\text{---} \\
\text{x = 4;} & & \text{plot(x,y);} \\
\text{y = 8;} & & \small\text{---} \\
\small\text{---} & & \small\text{---} \\
\small\text{---} & & \small\text{---}
\end{array}
$$

**Figure 2.9** Two tasks sharing a buffer with two variables.

$$
\begin{array}{c}
\tau_D \\
\tau_W
\end{array}
\begin{array}{c}
\text{------------------------------------------------------------------->} \\
\text{------------------------------------------------------------------->}
\end{array}
\begin{array}{c}
\text{plot(x,y)} \\
\fbox{R} \\
\text{} \\
\text{------------------------------------------------------------------->} \\
\text{x=4} \\
\fbox{R} \\
\text{} \\
\text{y=8} \\
\text{} \\
\fbox{R} \\
\text{(1,2)} \quad \text{(4,2)} \quad \text{(4,8)}
\end{array}
$$

**Figure 2.10** Example of schedule creating data inconsistency.

To better understand why mutual exclusion is important for guaranteeing data consistency, consider the application illustrated in Figure 2.9, where two tasks cooperate to track a moving object: task $\tau_W$ gets the object coordinates from a sensor and writes them into a shared buffer $R$, containing two variables $(x, y)$; task $\tau_D$ reads the variables from the buffer and plots a point on the screen to display the object trajectory.

If the access to the buffer is not mutually exclusive, task $\tau_W$ (having lower priority than $\tau_D$) may be preempted while updating the variables, so leaving the buffer in an inconsistent state. The situation is illustrated in Figure 2.10, where, at time $t$, the $(x, y)$ variables have values $(1, 2)$. If $\tau_W$ is preempted after updating $x$ and before updating $y$, $\tau_D$ will display the object in $(4, 2)$, which is neither the old nor the new position.

To ensure a correct access to exclusive resources, operating systems provide a synchronization mechanism (e.g., semaphores) that can be used to create critical sections of code. In the following, when we say that two or more tasks have resource constraints, we mean that they share resources that are accessed through a synchronization mechanism.

---

<!-- page 33 -->

# Basic Concepts

33

[FIGURE: Structure of two tasks, $\tau_W$ and $\tau_D$, interacting with a shared resource R and using wait(s)/signal(s) primitives to protect the critical section.]

**Figure 2.11** Structure of two tasks that share a mutually exclusive resource protected by a semaphore.

[FIGURE: Timeline showing the execution of tasks $\tau_D$ and $\tau_W$ over time, illustrating how semaphore protection prevents concurrent access to resource R, including time points (1,2), (4,2), and (4,8).]

**Figure 2.12** Example of schedule when the resource is protected by a semaphore.

To avoid the problem illustrated in Figure 2.10, both tasks have to encapsulate the instructions that manipulate the shared variables into a critical section. If a binary semaphore $s$ is used for this purpose, then each critical section must begin with a $\text{wait}(s)$ primitive and must end with a $\text{signal}(s)$ primitive, as shown in Figure 2.11.

If the resource is free, the $\text{wait}(s)$ primitive executed by $\tau_W$ notifies that a task is using the resource, which becomes locked until the task executes the $\text{signal}(s)$. Hence, if $\tau_D$ preempts $\tau_W$ inside the critical section, it is blocked as soon as it executes $\text{wait}(s)$ and the processor is given back to $\tau_W$. When $\tau_W$ exits its critical section by executing $\text{signal}(s)$, then $\tau_D$ is resumed and the processor is given to the ready task with the highest priority. The resulting schedule is shown in Figure 2.12.

---

<!-- page 34 -->

34
CHAPTER 2

[FIGURE: Waiting state caused by resource constraints, showing transitions between READY, RUN, and WAITING states via activation, scheduling, preemption, termination, signal free resource, and wait on busy resource.]

**Figure 2.13** Waiting state caused by resource constraints.

A task waiting for an exclusive resource is said to be **blocked** on that resource. All tasks blocked on the same resource are kept in a queue associated with the semaphore protecting the resource. When a running task executes a $\text{wait}$ primitive on a locked semaphore, it enters a $\text{waiting}$ state, until another task executes a $\text{signal}$ primitive that unlocks the semaphore. Note that when a task leaves the waiting state, it does not go in the running state, but in the ready state, so that the CPU can be assigned to the highest-priority task by the scheduling algorithm. The state transition diagram relative to the situation described above is shown in Figure 2.13.

### 2.3 DEFINITION OF SCHEDULING PROBLEMS

In general, to define a scheduling problem we need to specify three sets: a set of $n$ tasks $\Gamma = \{\tau_1, \tau_2, \ldots, \tau_n\}$, a set of $m$ processors $P = \{P_1, P_2, \ldots, P_m\}$ and a set of $s$ types of resources $R = \{R_1, R_2, \ldots, R_s\}$. Moreover, precedence relations among tasks can be specified through a directed acyclic graph, and timing constraints can be associated with each task. In this context, scheduling means assigning processors from $P$ and resources from $R$ to tasks from $\Gamma$ in order to complete all tasks under the specified constraints $[\text{B}^{+}93]$. This problem, in its general form, has been shown to be NP-complete [GJ79] and hence computationally intractable.

Indeed, the complexity of scheduling algorithms is of high relevance in dynamic real-time systems, where scheduling decisions must be taken on line during task execution. A *polynomial algorithm* is one whose time complexity grows as a polynomial function $p$ of the input length $n$ of an instance. The complexity of such algorithms is denoted by $O(p(n))$. Each algorithm whose complexity function cannot be bounded in that way is called an *exponential time algorithm*. In particular, $\text{NP}$ is the class of all decision problems that can be solved in polynomial time by a nondeterministic Turing machine.

---

<!-- page 35 -->

Basic Concepts

35

A problem $Q$ is said to be $\text{NP-complete}$ if $Q \in \mathbf{NP}$ and, for every $Q' \in \mathbf{NP}$, $Q'$ is polynomially transformable to $Q$ [GJ79]. A decision problem $Q$ is said to be $\text{NP-hard}$ if all problems in $\mathbf{NP}$ are polynomially transformable to $Q$, but we cannot show that $Q \in \mathbf{NP}$.

Let us consider two algorithms with complexity functions $n$ and $n^5$, respectively, and let us assume that an elementary step for these algorithms lasts $1 \mu\text{s}$. If the input length of the instance is $n = 30$, then it is easy to calculate that the polynomial algorithm can solve the problem in $30 \mu\text{s}$, whereas the other needs about $3 \cdot 10^5$ centuries. This example illustrates that the difference between polynomial and exponential time algorithms is large and, hence, it may have a strong influence on the performance of dynamic real-time systems. As a consequence, one of the research objectives in real-time scheduling is to identify simpler, but still practical, problems that can be solved in polynomial time.

To reduce the complexity of constructing a feasible schedule, one may simplify the computer architecture (for example, by restricting to the case of uniprocessor systems), or one may adopt a preemptive model, use fixed priorities, remove precedence and/or resource constraints, assume simultaneous task activation, homogeneous task sets (solely periodic or solely aperiodic activities), and so on. The assumptions made on the system or on the tasks are typically used to classify the various scheduling algorithms proposed in the literature.

### 2.3.1 CLASSIFICATION OF SCHEDULING ALGORITHMS

Among the great variety of algorithms proposed for scheduling real-time tasks, the following main classes can be identified:

*   **Preemptive vs. Non-preemptive.**
    *   In preemptive algorithms, the running task can be interrupted at any time to assign the processor to another active task, according to a predefined scheduling policy.
    *   In non-preemptive algorithms, a task, once started, is executed by the processor until completion. In this case, all scheduling decisions are taken as the task terminates its execution.

---

<!-- page 36 -->

36 | CHAPTER 2

* **Static vs. Dynamic.**
  - Static algorithms are those in which scheduling decisions are based on fixed parameters, assigned to tasks before their activation.
  - Dynamic algorithms are those in which scheduling decisions are based on dynamic parameters that may change during system evolution.

* **Off-line vs. Online.**
  - A scheduling algorithm is used off-line if it is executed on the entire task set before tasks activation. The schedule generated in this way is stored in a table and later executed by a dispatcher.
  - A scheduling algorithm is used online if scheduling decisions are taken at runtime every time a new task enters the system or when a running task terminates.

* **Optimal vs. Heuristic.**
  - An algorithm is said to be optimal if it minimizes some given cost function defined over the task set. When no cost function is defined and the only concern is to achieve a feasible schedule, then an algorithm is said to be optimal if it is able to find a feasible schedule, if one exists.
  - An algorithm is said to be heuristic if it is guided by a heuristic function in taking its scheduling decisions. A heuristic algorithm tends toward the optimal schedule, but does not guarantee finding it.

Moreover, an algorithm is said to be **clairvoyant** if it knows the future; that is, if it knows in advance the arrival times of all the tasks. Although such an algorithm does not exist in reality, it can be used for comparing the performance of real algorithms against the best possible one.

## GUARANTEE-BASED ALGORITHMS

In hard real-time applications that require highly predictable behavior, the feasibility of the schedule should be guaranteed in advance; that is, before task execution. In this way, if a critical task cannot be scheduled within its deadline, the system is still in time to execute an alternative action, attempting to avoid catastrophic consequences. In order to check the feasibility of the schedule before tasks’ execution, the system has to plan its actions by looking ahead in the future and by assuming a worst-case scenario.

---

<!-- page 37 -->

# Basic Concepts

In static real-time systems, where the task set is fixed and known a priori, all task activations can be precalculated off line, and the entire schedule can be stored in a table that contains all guaranteed tasks arranged in the proper order. Then, at runtime, a dispatcher simply removes the next task from the table and puts it in the running state. The main advantage of the static approach is that the runtime overhead does not depend on the complexity of the scheduling algorithm. This allows very sophis- ticated algorithms to be used to solve complex problems or find optimal scheduling sequences. On the other hand, however, the resulting system is quite inflexible to environmental changes; thus, predictability strongly relies on the observance of the hypotheses made on the environment.

In dynamic real-time systems (typically consisting of firm tasks), tasks can be created at runtime; hence the guarantee must be done *online* every time a new task is created. A scheme of the guarantee mechanism typically adopted in dynamic real-time systems is illustrated in Figure 2.14.

If $\Gamma$ is the current task set that has been previously guaranteed, a newly arrived task $\tau_{new}$ is accepted into the system if and only if the task set $\Gamma' = \Gamma \cup \{\tau_{new}\}$ is found schedulable. If $\Gamma'$ is not schedulable, then task $\tau_{new}$ is rejected to preserve the feasi- bility of the current task set.

It is worth noting that since the guarantee mechanism is based on worst-case assump- tions a task could unnecessarily be rejected. This means that the guarantee of firm tasks is achieved at the cost of lower efficiency. On the other hand, the benefit of having a guarantee mechanism is that potential overload situations can be detected in advance to avoid negative effects on the system. One of the most dangerous phenom- ena caused by a transient overload is called *domino effect*. It refers to the situation in which the arrival of a new task causes all previously guaranteed tasks to miss their deadlines. Let us consider for example the situation depicted in Figure 2.15, where five jobs are scheduled based on their absolute deadlines.

[FIGURE: Scheme of the guarantee mechanism used in dynamic real-time systems, showing states: activation, acceptance test, READY, RUNNING, WAITING, and transitions like scheduling, termination, preemption, wait on busy resource, signal free resource, and rejection.]

**Figure 2.14** Scheme of the guarantee mechanism used in dynamic real-time systems.

---

<!-- page 38 -->

38
CHAPTER 2

[FIGURE: A Gantt-like chart showing the scheduling of five jobs ($J_{\text{new}}, J_1, J_2, J_3, J_4$) over time ($t$). Dotted lines indicate time $t_0$. The execution of $J_{\text{new}}$ causes a delay in the execution blocks of $J_1, J_2, J_3,$ and $J_4$, pushing them past their original deadline points (indicated by downward arrows).]

**Figure 2.15 Example of domino effect.**

At time $t_0$, if job $J_{\text{new}}$ were accepted, all the other jobs (previously schedulable) would miss their deadlines. In planned-based algorithms, this situation is detected at time $t_0$, when the guarantee is performed, and causes job $J_{\text{new}}$ to be rejected.

In summary, the guarantee test ensures that, once a task is accepted, it will complete within its deadline and, moreover, its execution will not jeopardize the feasibility of the tasks that have been previously guaranteed.

## BEST-EFFORT ALGORITHMS

In certain real-time applications, computational activities have soft timing constraints that should be met whenever possible to satisfy system requirements. In these systems, missing soft deadlines do not cause catastrophic consequences, but only a performance degradation.

For example, in typical multimedia applications, the objective of the computing system is to handle different types of information (such as text, graphics, images, and sound) in order to achieve a certain quality of service for the users. In this case, the timing constraints associated with the computational activities depend on the quality of service requested by the users; hence, missing a deadline may only affect the performance of the system.

To efficiently support soft real-time applications that do not have hard timing requirements, a *best-effort* approach may be adopted for scheduling.

---

<!-- page 39 -->

# Basic Concepts
39

A best-effort scheduling algorithm tries to “do its best” to meet deadlines, but there is no guarantee of finding a feasible schedule. In a best-effort approach, tasks may be enqueued according to policies that take time constraints into account; however, since feasibility is not checked, a task may be aborted during its execution. On the other hand, best-effort algorithms perform much better than guarantee-based schemes in the average case. In fact, whereas the pessimistic assumptions made in the guarantee mechanism may unnecessarily cause task rejections, in best-effort algorithms a task is aborted only under real overload conditions.

## 2.3.2 METRICS FOR PERFORMANCE EVALUATION

The performance of scheduling algorithms is typically evaluated through a cost function defined over the task set. For example, classical scheduling algorithms try to minimize the average response time, the total completion time, the weighted sum of completion times, or the maximum lateness. When deadlines are considered, they are usually added as constraints, imposing that all tasks must meet their deadlines. If some deadline cannot be met with an algorithm $\mathcal{A}$, the schedule is said to be infeasible by $\mathcal{A}$. Table 2.1 shows some common cost functions used for evaluating the performance of a scheduling algorithm.

The metrics adopted in the scheduling algorithm has strong implications on the performance of the real-time system [SSDNB95], and it must be carefully chosen according to the specific application to be developed. For example, the average response time is generally not of interest for real-time applications, because there is not direct assessment of individual timing properties such as periods or deadlines. The same is true for minimizing the total completion time. The weighted sum of completion times is relevant when tasks have different importance values that they impart to the system on completion. Minimizing the maximum lateness can be useful at design time when resources can be added until the maximum lateness achieved on the task set is less than or equal to zero. In that case, no task misses its deadline. In general, however, minimizing the maximum lateness does not minimize the number of tasks that miss their deadlines and does not necessarily prevent one or more tasks from missing their deadline.

Let us consider, for example, the case depicted in Figure 2.16. The schedule shown in Figure 2.16a minimizes the maximum lateness, but all tasks miss their deadline. On the other hand, the schedule shown in Figure 2.16b has a greater maximum lateness, but four tasks out of five complete before their deadline.

---

<!-- page 40 -->

40
CHAPTER 2

| | |
| :--- | :--- |
| **Average response time:** | $$\bar{t}_r = \frac{1}{n}\sum_{i=1}^{n}(f_i - a_i)$$ |
| **Total completion time:** | $$t_c = \max_i(f_i) - \min_i(a_i)$$ |
| **Weighted sum of completion times:** | $$t_w = \sum_{i=1}^{n}w_i f_i$$ |
| **Maximum lateness:** | $$L_{\max} = \max_i(f_i - d_i)$$ |
| **Maximum number of late tasks:** | $$N_{\text{late}} = \sum_{i=1}^{n}\text{miss}(f_i)$$ |
| where | $$\text{miss}(f_i) = \begin{cases} 0 & \text{if } f_i \leq d_i \\ 1 & \text{otherwise} \end{cases}$$ |

**Table 2.1** Example of cost functions.

---

<!-- page 41 -->

# Basic Concepts
**41**

[FIGURE: Gantt charts for two schedules (a) and (b) for five tasks $J_1$ through $J_5$, showing deadlines $d_i$ and lateness/earliness $L_i$. In (a), $L_{\max} = L_1 = 3$. In (b), $L_{\max} = L_1 = 23$.]

**Figure 2.16** The schedule in (a) minimizes the maximum lateness, but all tasks miss their deadline. The schedule in (b) has a greater maximum lateness, but four tasks out of five complete before their deadline.

When tasks have soft deadlines and the application goal is to meet as many deadlines as possible (without a priori guarantee), then the scheduling algorithm should use a cost function that minimizes the number of late tasks.

In other applications, the benefit of executing a task may depend not only on the task importance but also on the time at which it is completed. This can be described by means of specific *utility functions*, which describe the value associated with the task as a function of its completion time.

Figure 2.17 illustrates some typical utility functions that can be defined on the application tasks. For instance, non-real-time tasks (a) do not have deadlines, thus the value achieved by the system is proportional to the task importance and does not depend on the completion time. Soft tasks (b) have noncritical deadlines; therefore, the value gained by the system is constant if the task finishes before its deadline but decreases with the exceeding time. In some cases (c), it is required to execute a task *on-time*, that is, not too early and not too late with respect to a given deadline. Hence, the value achieved by the system is high if the task is completed around the deadline, but it rapidly decreases with the absolute value of the lateness. Such types of constraints are typical when playing notes, since the human ear is quite sensitive to time jitter.

---

<!-- page 42 -->

42 CHAPTER 2

[FIGURE: Four graphs illustrating utility functions $v(f_i)$ versus finish time $f_i$ for four task types (non real-time, soft, on-time, and firm) relative to a deadline $d_i$.]

**Figure 2.17** Example of cost functions for different types of tasks.

In other cases (d), executing a task after its deadline does not cause catastrophic consequences, but there is no benefit for the system, thus the utility function is zero after the deadline.

When utility functions are defined on the tasks, the performance of a scheduling algorithm can be measured by the *cumulative value*, given by the sum of the utility functions computed at each completion time:
$$
\text{Cumulative\_value} = \sum_{i=1}^{n} v(f_i).
$$
This type of metrics is very useful for evaluating the performance of a system during overload conditions, and it is considered in more detail in Chapter 9.

## 2.4 SCHEDULING ANOMALIES

In this section we describe some singular examples that clearly illustrate that real-time computing is not equivalent to fast computing, since, for example, an increase of computational power in the supporting hardware does not always cause an improvement of performance. These particular situations, called Richard’s anomalies, were described by Graham in 1976 and refer to task sets with precedence relations executed in a multiprocessor environment.

---

<!-- page 43 -->

# Basic Concepts

43

[FIGURE: Precedence graph of the task set $J$; numbers in parentheses indicate computation times.]

$$\begin{array}{cccc}
J_{1} & (3) & \bigcirc & \longrightarrow & \bigcirc & J_{9} & (9) \\
J_{2} & (2) & \bigcirc & \longrightarrow & \bigcirc & J_{8} & (4) \\
& & & \nearrow & \bigcirc & J_{7} & (4) \\
J_{3} & (2) & \bigcirc & \searrow & \bigcirc & J_{6} & (4) \\
J_{4} & (2) & \bigcirc & \longrightarrow & \bigcirc & J_{5} & (4)
\end{array}$$
$$\text{priority}(J_{i}) > \text{priority}(J_{j}) \quad \forall i < j$$

**Figure 2.18** Precedence graph of the task set $J$; numbers in parentheses indicate computation times.

Designers should be aware of such insidious anomalies to take the proper countermeasures to avoid them. The most important anomalies are expressed by the following theorem [Gra76, SSDNB95]:

**Theorem 2.1 (Graham, 1976)** *If a task set is optimally scheduled on a multiprocessor with some priority assignment, a fixed number of processors, fixed execution times, and precedence constraints, then increasing the number of processors, reducing execution times, or weakening the precedence constraints can increase the schedule length.*

This result implies that, if tasks have deadlines, then adding resources (for example, an extra processor) or relaxing constraints (less precedence among tasks or fewer execution times requirements) can make things worse. A few examples can best illustrate why this theorem is true.

Let us consider a task set consisting of nine jobs $J = \{J_{1}, J_{2}, \dots, J_{9}\}$, sorted by decreasing priorities, so that $J_{i}$ priority is greater than $J_{j}$ priority if and only if $i < j$. Moreover, jobs are subject to precedence constraints that are described through the graph shown in Figure 2.18. Computation times are indicated in parentheses.

If this task set is executed on a parallel machine with three processors, where the highest priority task is assigned to the first available processor, the resulting schedule $\sigma^{*}$ is illustrated in Figure 2.19, where the global completion time is $t_{c} = 12$ units of time.

---

<!-- page 44 -->

44
CHAPTER 2

[FIGURE: Gantt chart representing the optimal schedule of task set $J$ on a three-processor machine. Tasks $J_1, J_9$ on $P_1$; $J_2, J_4, J_5, J_7$ on $P_2$; $J_3, J_6, J_8$ on $P_3$. Completion time is 12.]

**Figure 2.19** Optimal schedule of task set $J$ on a three-processor machine.

[FIGURE: Gantt chart representing the schedule of task set $J$ on a four-processor machine. Tasks $J_1, J_8$ on $P_1$; $J_2, J_5, J_9$ on $P_2$; $J_3, J_6$ on $P_3$; $J_4, J_7$ on $P_4$. Completion time is 15.]

**Figure 2.20** Schedule of task set $J$ on a four-processor machine.

Now we will show that adding an extra processor, reducing tasks’ execution times, or weakening precedence constraints will increase the global completion time of the task set.

## NUMBER OF PROCESSORS INCREASED

If we execute the task set $J$ on a more powerful machine consisting of four processors, we obtain the schedule illustrated in Figure 2.20, which is characterized by a global completion time of $t_c = 15$ units of time.

## COMPUTATION TIMES REDUCED

One could think that the global completion time of the task set $J$ could be improved by reducing tasks’ computation times of each task. However, we can surprisingly see that, reducing the computation time of each task by one unit of time, the schedule length will increase with respect to the optimal schedule $\sigma^*$, and the global completion time will be $t_c = 13$, as shown in Figure 2.21.

---

<!-- page 45 -->

# Basic Concepts

45

[FIGURE: Gantt chart showing the schedule of task set $J$ on three processors $P_1, P_2, P_3$, illustrating task execution times from $t=0$ to $t=15$. Tasks $J_1, J_5, J_8$ are on $P_1$; $J_2, J_4, J_6, J_9$ are on $P_2$; $J_3, J_7$ are on $P_3$.]

**Figure 2.21** Schedule of task set $J$ on three processors, with computation times reduced by one unit of time.

$$
\begin{array}{ccccc}
J_{1}^{(3)} & \longrightarrow & & J_{9}^{(9)} \\
J_{2}^{(2)} & \bigcirc & & J_{8}^{(4)} \\
J_{3}^{(2)} & \bigcirc & & J_{7}^{(4)} \\
J_{4}^{(2)} & \bigcirc & \longrightarrow & J_{6}^{(4)} \\
& & & J_{5}^{(4)}
\end{array}
$$
(a)

[FIGURE: Gantt chart showing an alternative schedule of task set $J$ on three processors $P_1, P_2, P_3$, illustrating task execution times from $t=0$ to $t=16$. Tasks $J_1, J_8, J_9$ are on $P_1$; $J_2, J_4, J_5$ are on $P_2$; $J_3, J_7, J_6$ are on $P_3$.]

(b)

**Figure 2.22** **a.** Precedence graph of task set $J$ obtained by removing the constraints on tasks $J_7$ and $J_8$. **b.** Schedule of task set $J$ on three processors, with precedence constraints weakened.

# PRECEDENCE CONSTRAINTS WEAKENED

Scheduling anomalies can also arise by removing precedence constraints from the directed acyclic graph depicted in Figure 2.18. For instance, removing the precedence relations between job $J_4$ and jobs $J_7$ and $J_8$ (see Figure 2.22a), we obtain the schedule shown in Figure 2.22b, which is characterized by a global completion time of $t_c = 16$ units of time.

---

<!-- page 46 -->

```markdown
46
CHAPTER 2

[FIGURE: Gantt chart showing two parallel schedules for jobs $J_1, J_2, J_3, J_4, J_5$ on two processors $P_1$ and $P_2$. In (a), $J_1$ and $J_2$ are on $P_1$, $J_3, J_4, J_5$ are on $P_2$. The total completion time is $t_c=17$. In (b), the schedule changes, and the total completion time is $t_c=22$.]

**Figure 2.23** Example of anomaly under resource constraints. If $J_2$ and $J_4$ share the same resource in exclusive mode, the optimal schedule length (a) increases if the computation time of job $J_1$ is reduced (b). Jobs are statically allocated on the processors.

# ANOMALIES UNDER RESOURCE CONSTRAINTS

The following example shows that, in the presence of shared resources, the schedule length of a task set can increase when reducing tasks’ computation times. Consider the case illustrated in Figure 2.23, where five jobs are statically allocated on two processors: jobs $J_1$ and $J_2$ on processor P1, and jobs $J_3$, $J_4$ and $J_5$ on processor P2 (jobs are indexed by decreasing priority). Moreover, jobs $J_2$ and $J_4$ share the same resource in exclusive mode; hence their execution cannot overlap in time. A schedule of this task set is shown in Figure 2.23a, where the total completion time is $t_c = 17$.

If we now reduce the computation time of job $J_1$ on the first processor, then $J_2$ can begin earlier and take the resource before $J_4$. As a consequence, job $J_4$ must now block over the shared resource and possibly miss its deadline. This situation is illustrated in Figure 2.23b. As we can see, the blocking time experienced by $J_4$ causes a delay in the execution of $J_5$ (which may also miss its deadline), increasing the total completion time of the task set from 17 to 22.
```

---

<!-- page 47 -->

# Basic Concepts

Notice that the scheduling anomaly illustrated by the previous example is particularly insidious for hard real-time systems, because tasks are guaranteed based on their worst-case behavior, but they may complete before their worst-case computation time. A simple solution that avoids the anomaly is to keep the processor idle if tasks complete earlier, but this can be very inefficient. There are algorithms, such as the one proposed by Shen [SRS93], that tries to reclaim such an idle time, while addressing the anomalies so that they will not occur.

If tasks share mutually exclusive resources, scheduling anomalies can also occur in a uniprocessor system when changing the processor speed [But06]. In particular, the anomaly can be expressed as follows:

> A real-time application that is feasible on a given processor can become infeasible when running on a faster processor.

Figure 2.24 illustrates a simple example where two tasks, $\tau_1$ and $\tau_2$, share a common resource (critical sections are represented by light grey areas). Task $\tau_1$ has a higher priority, arrives at time $t=2$ and has a relative deadline $D_1 = 7$. Task $\tau_2$, having lower priority, arrives at time $t=0$ and has a relative deadline $D_2 = 23$. Suppose that, when the tasks are executed at a certain speed $S_1$, $\tau_1$ has a computation time $C_1 = 6$, (where 2 units of time are spent in the critical section), whereas $\tau_2$ has a computation time $C_2 = 18$ (where 12 units of time are spent in the critical section). As shown in Figure 2.24a, if $\tau_1$ arrives just before $\tau_2$ enters its critical section, it is able to complete before its deadline, without experiencing any blocking. However, if the same task set is executed at a double speed $S_2 = 2S_1$, $\tau_1$ misses its deadline, as clearly illustrated in Figure 2.24b. This happens because, when $\tau_1$ arrives, $\tau_2$ already granted its resource, causing an extra blocking in the execution of $\tau_1$, due to mutual exclusion.

Although the average response time of the task set is reduced on the faster processor (from 14 to 9.5 units of time), note that the response time of task $\tau_1$ increases when doubling the speed, because of the extra blocking on the shared resource.

## ANOMALIES UNDER NON-PREEMPTIVE SCHEDULING

Similar situations can occur in non-preemptive scheduling. Figure 2.25 illustrates an anomalous behavior occurring in a set of three real-time tasks, $\tau_1, \tau_2$ and $\tau_3$, running in a non-preemptive fashion. Tasks are assigned a fixed priority proportional to their relative deadline, thus $\tau_1$ is the task with the highest priority and $\tau_3$ is the task with the lowest priority. As shown in Figure 2.25a, when tasks are executed at speed $S_1$, $\tau_1$ has a computation time $C'_1 = 2$ and completes at time $t=6$. However, if the same

---

<!-- page 48 -->

48
CHAPTER 2

[FIGURE: Scheduling anomaly diagram with two subplots (a) and (b) showing the execution timeline for tasks $\tau_1$ and $\tau_2$ under different processor speeds.]

**Figure 2.24** Scheduling anomaly in the presence of resource constraints: task $\tau$ meets its deadline when the processor is executing at a certain speed $S_1$ (a), but misses its deadline when the speed is doubled (b).

task set is executed with double speed $S_2 = 2S_1$, $\tau_1$ misses its deadline, as clearly illustrated in Figure 2.25b. This happens because, when $\tau_1$ arrives, $\tau_3$ already started its execution and cannot be preempted (due to the non-preemptive mode).

It is worth observing that a set of non-preemptive tasks can be considered as a special case of a set of tasks sharing a single resource (the processor) for their entire execution. According to this view, each task execution as it were inside a big critical section with a length equal to the task computation time. Once a task starts executing, it behaves as if it were locking a common semaphore, thus preventing all the other tasks from taking the processor.

---

<!-- page 49 -->

# Basic Concepts

49

[FIGURE: Two scheduling diagrams (a) and (b) for three preemptive tasks $\tau_1, \tau_2, \tau_3$ based on time intervals 0 to 18. Diagram (a) shows $\tau_1$ executing from 3 to 6, $\tau_2$ from 0 to 3, and $\tau_3$ from 6 to 15. Diagram (b) shows a deadline miss for $\tau_1$ when the processor speed is doubled.]

**Figure 2.25** Scheduling anomaly in the presence of non-preemptive tasks: task $\pi$ meets
its deadline when the processor is executing at speed $S_1$ (a), but misses its deadline when
the speed is doubled (b).

## ANOMALIES USING A DELAY PRIMITIVE

Another timing anomaly can occur when tasks using shared resources explicitly sus-
pend themselves through a $\text{delay}(T)$ system call, which suspends the execution of the
calling task for $T$ units of time. Figure 2.26a shows a case in which $\tau_1$ is feasible and
has a slack time of 6 units when running at the highest priority, suggesting that it could
easily tolerate a delay of two units. However, if $\tau_1$ executes a $\text{delay}(2)$ at time $t=2$,
it gives the opportunity to $\tau_2$ to lock the shared resource. Hence, when $\tau_1$ resumes,
it has to block on the semaphore for 7 units, thus missing its deadline, as shown in
Figure 2.26b.