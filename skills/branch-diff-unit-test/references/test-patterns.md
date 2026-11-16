# Test Patterns — 常用測試模式

## 基本結構：Given / When / Then

所有測試遵循 Given-When-Then 結構，並用反引號命名法清楚描述情境：

```kotlin
@Test
fun `methodName_givenCondition_thenExpectedResult`() {
    // given
    val input = ...
    every { dependency.method() } returns value

    // when
    val result = sut.method(input)

    // then
    assertEquals(expected, result)
}
```

---

## ViewModel + StateFlow 標準模板

```kotlin
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(JUnit4::class)
class UserViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    @get:Rule
    val instantTaskExecutorRule = InstantTaskExecutorRule()

    private val userRepository: UserRepository = mockk()
    private lateinit var sut: UserViewModel

    @Before
    fun setUp() {
        sut = UserViewModel(userRepository)
    }

    @After
    fun tearDown() {
        unmockkAll()
    }

    // Happy path
    @Test
    fun `loadUser_withValidId_emitsSuccessState`() = runTest {
        // given
        val userId = "123"
        val user = User(id = userId, name = "Alice")
        coEvery { userRepository.getUser(userId) } returns Result.success(user)

        // when
        sut.loadUser(userId)
        advanceUntilIdle()

        // then
        assertEquals(UiState.Success(user), sut.uiState.value)
    }

    // Error path
    @Test
    fun `loadUser_whenRepositoryFails_emitsErrorState`() = runTest {
        // given
        val userId = "invalid"
        coEvery { userRepository.getUser(userId) } returns Result.failure(IOException("Network error"))

        // when
        sut.loadUser(userId)
        advanceUntilIdle()

        // then
        assertTrue(sut.uiState.value is UiState.Error)
    }

    // Null / Edge case
    @Test
    fun `loadUser_withNullId_emitsErrorState`() = runTest {
        // when
        sut.loadUser(null)

        // then
        assertTrue(sut.uiState.value is UiState.Error)
    }

    // StateFlow 發射序列（Turbine）
    @Test
    fun `loadUser_emitsLoadingThenSuccess`() = runTest {
        // given
        coEvery { userRepository.getUser(any()) } coAnswers {
            delay(100)
            Result.success(mockUser)
        }

        // when / then
        sut.uiState.test {
            assertEquals(UiState.Idle, awaitItem())
            sut.loadUser("123")
            assertEquals(UiState.Loading, awaitItem())
            assertEquals(UiState.Success(mockUser), awaitItem())
            cancelAndIgnoreRemainingEvents()
        }
    }
}
```

---

## UseCase 測試模板

```kotlin
@OptIn(ExperimentalCoroutinesApi::class)
class GetUserUseCaseTest {

    private val userRepository: UserRepository = mockk()
    private lateinit var sut: GetUserUseCase

    @Before
    fun setUp() {
        sut = GetUserUseCase(userRepository)
    }

    @Test
    fun `invoke_withValidUserId_returnsUser`() = runTest {
        // given
        coEvery { userRepository.getUser("123") } returns Result.success(mockUser)

        // when
        val result = sut("123")

        // then
        assertTrue(result.isSuccess)
        assertEquals(mockUser, result.getOrNull())
    }

    @Test
    fun `invoke_withEmptyId_returnsFailure`() = runTest {
        // when
        val result = sut("")

        // then
        assertTrue(result.isFailure)
        // Repository 不應被呼叫
        coVerify(exactly = 0) { userRepository.getUser(any()) }
    }

    @Test
    fun `invoke_whenRepositoryThrows_propagatesException`() = runTest {
        // given
        coEvery { userRepository.getUser(any()) } throws IOException("Network error")

        // when
        val result = sut("123")

        // then
        assertTrue(result.isFailure)
        assertTrue(result.exceptionOrNull() is IOException)
    }
}
```

---

## Repository 測試模板

```kotlin
class UserRepositoryImplTest {

    private val remoteDataSource: RemoteDataSource = mockk()
    private val localDataSource: LocalDataSource = mockk()
    private lateinit var sut: UserRepositoryImpl

    @Before
    fun setUp() {
        sut = UserRepositoryImpl(remoteDataSource, localDataSource)
    }

    // Cache-first 策略
    @Test
    fun `getUser_whenCacheAvailable_returnsCacheWithoutNetwork`() = runTest {
        // given
        every { localDataSource.getUser("123") } returns cachedUser

        // when
        val result = sut.getUser("123")

        // then
        assertEquals(cachedUser, result.getOrNull())
        coVerify(exactly = 0) { remoteDataSource.fetchUser(any()) }
    }

    // Cache miss → remote
    @Test
    fun `getUser_whenCacheMissAndNetworkAvailable_fetchesAndCaches`() = runTest {
        // given
        every { localDataSource.getUser("123") } returns null
        coEvery { remoteDataSource.fetchUser("123") } returns remoteUser
        every { localDataSource.saveUser(remoteUser) } just Runs

        // when
        val result = sut.getUser("123")

        // then
        assertEquals(remoteUser, result.getOrNull())
        verify { localDataSource.saveUser(remoteUser) }
    }

    // Network failure
    @Test
    fun `getUser_whenNetworkFailsAndNoCache_returnsFailure`() = runTest {
        // given
        every { localDataSource.getUser("123") } returns null
        coEvery { remoteDataSource.fetchUser("123") } throws IOException()

        // when
        val result = sut.getUser("123")

        // then
        assertTrue(result.isFailure)
    }
}
```

---

## Sealed Class 全分支測試

```kotlin
// UiState = Loading | Success<T> | Error(message) | Empty
@Test
fun `handleState_Loading_showsProgressIndicator`() {
    sut.handleState(UiState.Loading)
    verify { view.showProgress(true) }
}

@Test
fun `handleState_Success_displaysData`() {
    sut.handleState(UiState.Success(mockData))
    verify { view.showData(mockData) }
}

@Test
fun `handleState_Error_displaysErrorMessage`() {
    sut.handleState(UiState.Error("Something went wrong"))
    verify { view.showError("Something went wrong") }
}

@Test
fun `handleState_Empty_showsEmptyView`() {
    sut.handleState(UiState.Empty)
    verify { view.showEmptyView() }
}
```

---

## Flow / LiveData 輸出驗證

### Flow（需要 Turbine 或 toList collect）
```kotlin
@Test
fun `searchUsers_emitsMatchingResults`() = runTest {
    // given
    every { localDataSource.searchUsers("alice") } returns flowOf(listOf(user1, user2))

    // when / then
    sut.searchUsers("alice").test {
        assertEquals(listOf(user1, user2), awaitItem())
        awaitComplete()
    }
}
```

### LiveData
```kotlin
@Test
fun `userLiveData_updatesOnLoad`() {
    // given
    coEvery { repository.getUser(any()) } returns Result.success(mockUser)

    // when
    sut.loadUser("123")

    // then（InstantTaskExecutorRule 確保同步執行）
    assertEquals(mockUser, sut.userLiveData.value)
}
```

---

## 常見錯誤路徑模板

```kotlin
// IOException（網路錯誤）
@Test
fun `method_onNetworkError_returnsFailure`() = runTest {
    coEvery { dependency.networkCall() } throws IOException("No internet")
    val result = sut.method()
    assertTrue(result.isFailure)
}

// 空列表輸入
@Test
fun `process_withEmptyList_returnsEmptyResult`() = runTest {
    val result = sut.process(emptyList())
    assertTrue(result.isEmpty())
}

// Timeout
@Test
fun `fetchData_onTimeout_returnsError`() = runTest {
    coEvery { dependency.slowFetch() } coAnswers {
        delay(Long.MAX_VALUE)
        mockData
    }
    withTimeout(1000) {
        val result = sut.fetchData()
        assertTrue(result.isFailure)
    }
}
```
